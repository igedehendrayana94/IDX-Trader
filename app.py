import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

import idx
import ml
import timing
import ui
from texts import COLS, COND, GLOSSARY, T

st.set_page_config(page_title="IDX Trader", page_icon=":material/candlestick_chart:", layout="wide")

FOREIGN_DIR = Path(__file__).parent / "data" / "foreign"
POSITIONS = Path(__file__).parent / "data" / "positions.json"
FOREIGN_MIN_DAYS = 60  # fewer days = feature mostly empty in training, no point using it

# ---------- sidebar: only the 2 choices a beginner must make are visible ----------
with st.sidebar:
    lang = st.segmented_control("Language / Bahasa", ["id", "en"], default="id", required=True,
                                format_func=lambda k: {"id": "Indonesia", "en": "English"}[k])
t, cond_text, col_text = T[lang], COND[lang], COLS[lang]


def num(x, dec=0):
    """Indonesian uses '.' for thousands and ',' for decimals."""
    s = f"{x:,.{dec}f}"
    return s.translate(str.maketrans(",.", ".,")) if lang == "id" else s


def pct(x, dec=0):
    return f"{num(x, dec)}%"


with st.sidebar:
    mode = st.radio(t["mode"], ["swing", "daily"], format_func=lambda m: t[m],
                    captions=[t["swing_cap"], t["daily_cap"]])
    # text box instead of number_input: number_input cannot show thousand separators (10.000.000)
    digits = re.sub(r"\D", "", st.session_state.get("capital_txt", "10000000"))
    st.session_state.capital_txt = num(int(digits)) if digits else ""
    st.text_input(t["capital"], key="capital_txt", placeholder=t["capital_ph"], help=t["capital_help"])
    st.caption(t["capital_ph"])
    capital = int(digits) if digits else 0
    if capital < 1_000_000:
        st.error(t["capital_min"], icon=":material/error:")
        st.stop()
    with st.expander(t["advanced"], icon=":material/tune:"):
        max_alloc = st.slider(t["alloc"], 5, 100, 25, 5, help=t["alloc_help"]) / 100
        min_value = st.number_input(t["min_value"], min_value=0.0, value=5.0, step=1.0,
                                    help=t["min_value_help"]) * 1e9
        codes = st.text_area(t["universe"], " ".join(idx.UNIVERSE), height=160)
        use_ihsg = st.checkbox(t["use_ihsg"], value=True)
    refresh = st.button(t["refresh"], icon=":material/refresh:", width="stretch")
    st.caption(t["rules"].format(loss=pct(idx.MAX_LOSS * 100), buy=pct(idx.BUY_FEE * 100, 2),
                                 sell=pct(idx.SELL_FEE * 100, 2)))


@st.cache_data(ttl=3600, show_spinner=False)
def load(code_list):
    now = datetime.now(timing.WIB)
    return {c: timing.drop_unfinished(d, now) for c, d in idx.fetch(list(code_list), period="5y").items()}


@st.cache_data(ttl=3600, show_spinner=False)
def load_ihsg():
    return timing.drop_unfinished(idx.fetch_ihsg(period="5y"), datetime.now(timing.WIB))


@st.cache_data(ttl=3600, show_spinner=False)
def load_foreign():
    return idx.load_foreign(FOREIGN_DIR)


@st.cache_data(ttl=300, show_spinner=False)
def load_tv(codes, interval):
    return idx.tv_ratings(list(codes), interval)


@st.cache_data(ttl=3600, show_spinner=False)
def train(code_list, mode, use_ihsg, use_foreign):
    p = ml.dataset(load(code_list), mode, ihsg=load_ihsg() if use_ihsg else None,
                   foreign=load_foreign() if use_foreign else None)
    return ml.walk_forward(p, mode), ml.predict_latest(p)


if refresh:
    for f in (load, load_ihsg, load_foreign, train):
        f.clear()

# ---------- data ----------
code_list = tuple(sorted({c.strip().upper() for c in codes.split() if c.strip()}))
with st.spinner(t["downloading"]):
    data, ihsg = load(code_list), load_ihsg()
df = idx.screen(data, mode, capital, max_alloc, min_value)
foreign_days = load_foreign()["date"].nunique()
use_foreign = foreign_days >= FOREIGN_MIN_DAYS
if not df.empty:
    with st.spinner(t["training"]):
        wf, prob = train(code_list, mode, use_ihsg, use_foreign)
    df.insert(4, "ml_prob", df["code"].map(prob).round(3))
    auc = wf["auc"].mean() if len(wf) else 0.5
    base_win = wf["base_win%"].mean() if len(wf) else float("nan")
    has_edge = auc >= 0.53  # shortcut: fixed AUC bar, replace with a significance test if folds grow
cond_keys = list(idx.conditions(idx.indicators(next(iter(data.values()))), mode).columns) if data else []

# ---------- header: the answer first ----------
st.title("IDX Trader")
st.caption(t["subtitle"])
missing = set(code_list) - set(data)
if missing:
    st.warning(t["no_data"] + " ".join(sorted(missing)), icon=":material/warning:")
if df.empty:
    st.info(t["no_liquid"], icon=":material/info:")
    st.stop()

def day_name(d):
    return f"{t['days'][d.weekday()]}, {d.strftime('%d-%m-%Y')}"


now = datetime.now(timing.WIB)
phase, when = timing.market_status(now)
when_txt = (t["opens"].format(when=f"{day_name(when)} {when:%H:%M}") if phase == "closed"
            else t["until"].format(when=f"{when:%H:%M}"))
st.caption(f":material/event: {t['kpi_date']} {df['date'].max().strftime('%d-%m-%Y')}  ·  "
           f":material/schedule: **{t['phase'][phase]}** · {when_txt} WIB")
buys = df[df["signal"] & (df["lots"] > 0)]


def tv_line(code, tv_d, tv_m):
    """One-line TradingView second opinion, or nothing when TradingView has no data."""
    d, m = tv_d.get(code), tv_m.get(code)
    if not d:
        return
    st.markdown(t["tv_line"].format(d=t["tv_rec"][d["rec"]], m=t["tv_rec"][m["rec"]] if m else "-",
                                    b=d["buy"], n=d["neutral"], s=d["sell"]), help=t["tv_note"])


def stock_row(code, chip=None):
    """Watchlist row from price history: last close, change vs previous close, 30-day sparkline."""
    c = data[code]["Close"] if code in data else ihsg["Close"]
    name = t["ihsg_name"] if code == "IHSG" else idx.NAMES.get(code, "")
    return ui.row(code, name, c.tail(30), c.iloc[-1], c.iloc[-1] - c.iloc[-2],
                  (c.iloc[-1] / c.iloc[-2] - 1) * 100, num, chip)


st.html(ui.CSS)
st.markdown(stock_row("IHSG"), unsafe_allow_html=True)
st.markdown(ui.stats([(t["kpi_buys"], str(len(buys))),
                      (t["kpi_ml"], t["ml_on"] if has_edge else t["ml_off"])]), unsafe_allow_html=True)

tab_rec, tab_pos, tab_ml, tab_all, tab_guide = st.tabs([
    f":material/thumb_up: {t['tab_rec']}", f":material/work: {t['tab_pos']}", f":material/psychology: {t['tab_ml']}",
    f":material/format_list_bulleted: {t['tab_all']}", f":material/school: {t['tab_guide']}",
])

# ---------- recommendations ----------
with tab_rec:
    st.markdown(t["rec_intro"].format(n=len(cond_keys), mode=t[mode]))
    tv_codes = tuple(buys["code"])
    tv_d, tv_m = (load_tv(tv_codes, "1d"), load_tv(tv_codes, "15m")) if tv_codes else ({}, {})
    for _, r in buys.iterrows():
        with st.container(border=True):
            st.markdown(stock_row(r["code"], (t["buy"].upper(), "up")), unsafe_allow_html=True)
            target_pct = (r["target"] / r["entry"] - 1) * 100
            st.markdown(ui.ticket([
                (t["entry"], num(r["entry"])),
                (t["stop"], f"{num(r['stop'])} ({pct(r['loss%'], 2)})", "down"),
                (t["target"], f"{num(r['target'])} (+{pct(target_pct, 2)})", "up"),
                (t["lots"], f"{num(r['lots'])} lot = {num(r['lots'] * idx.LOT)} {'lembar' if lang == 'id' else 'shares'}"),
                (t["total"], f"Rp {num(r['cost_rp'])}"),
                (t["maxloss"], f"Rp {num(r['max_loss_rp'])} ({pct(r['max_loss_rp'] / capital * 100, 1)} {t['of_capital']})",
                 "down"),
            ]), unsafe_allow_html=True)
            st.markdown(f"**{t['why']}**")
            st.markdown("  \n".join(f":material/check_circle: {cond_text[k]}" for k in cond_keys))
            st.markdown(t["ml_line"].format(prob=pct(r["ml_prob"] * 100), base=pct(base_win))
                        if has_edge else t["ml_skip"])
            tv_line(r["code"], tv_d, tv_m)
            st.caption(t["history"].format(n=r["bt_trades"], win=pct(r["bt_win%"]), avg=pct(r["bt_avg%"], 2))
                       if r["bt_trades"] else t["history_none"])
            if r["bt_trades"] and r["bt_avg%"] < 0:
                st.warning(t["history_bad"], icon=":material/warning:")
            sch = timing.schedule(r["date"], mode)
            st.markdown(f"**{t['plan_title']}**")
            st.markdown(ui.ticket([
                (t["plan_buy"], t["plan_buy_v"].format(day=day_name(sch["buy_day"]), price=num(r["entry"]))),
                (t["plan_protect"], t["plan_protect_v"].format(stop=num(r["stop"]), target=num(r["target"]))),
                (t["plan_check"], t["plan_check_v"]),
                (t["plan_exit"], t["plan_exit_v"].format(day=day_name(sch["exit_deadline"])), "down"),
            ]), unsafe_allow_html=True)
            st.link_button(t["cta_buy"].format(code=r["code"]), f"https://stockbit.com/symbol/{r['code']}",
                           icon=":material/open_in_new:", type="primary", width="stretch")

    if buys.empty:
        st.info(f"**{t['none_title']}** {t['none_body']}", icon=":material/hourglass_empty:")
    no_money = df[df["signal"] & (df["lots"] == 0)]
    if len(no_money):
        st.warning(t["zero_lots"].format(codes=", ".join(no_money["code"])), icon=":material/savings:")

    near = df[~df["signal"] & (df["score"] == len(cond_keys) - 1)].head(6)
    if len(near):
        st.subheader(t["near_title"], anchor=False)
        st.caption(t["near_intro"])
        html = ""
        for _, r in near.iterrows():
            miss = next(k for k in cond_keys if not r[k])
            html += stock_row(r["code"], (t["near_missing"].format(cond=cond_text[miss].split(":")[0]), "flat"))
        st.markdown(html, unsafe_allow_html=True)

# ---------- my positions ----------
def read_positions():
    try:
        return json.loads(POSITIONS.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_positions(rows):
    POSITIONS.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS.write_text(json.dumps(rows, indent=1))


with tab_pos:
    positions = read_positions()
    with st.expander(t["add_pos"], icon=":material/add:", expanded=not positions):
        with st.form("add_position", clear_on_submit=True, border=False):
            f1, f2 = st.columns(2)
            p_code = f1.selectbox(t["pos_code"], sorted(data))
            p_mode = f2.radio(t["pos_mode"], ["swing", "daily"], format_func=lambda m: t[m], horizontal=True,
                              index=0 if mode == "swing" else 1)
            f3, f4, f5 = st.columns(3)
            p_date = f3.date_input(t["pos_date"], value=now.date(), max_value=now.date(), format="DD/MM/YYYY")
            p_price = f4.number_input(t["pos_price"], min_value=0, step=5)
            p_lots = f5.number_input(t["pos_lots"], min_value=0, step=1)
            if st.form_submit_button(t["pos_save"], icon=":material/save:", type="primary"):
                if p_price > 0 and p_lots >= 1 and p_date <= now.date():
                    positions.append({"code": p_code, "mode": p_mode, "date": p_date.isoformat(),
                                      "price": float(p_price), "lots": int(p_lots)})
                    write_positions(positions)
                    st.success(t["pos_saved"], icon=":material/check:")
                else:
                    st.error(t["pos_bad"], icon=":material/error:")
    if not positions:
        st.info(t["pos_none"], icon=":material/info:")
    pos_codes = tuple(sorted({p["code"] for p in positions}))
    pos_tv_d, pos_tv_m = (load_tv(pos_codes, "1d"), load_tv(pos_codes, "15m")) if pos_codes else ({}, {})
    for i, p in enumerate(positions):
        buy_day = datetime.fromisoformat(p["date"]).date()
        if p["code"] not in data:
            st.warning(t["no_data"] + p["code"], icon=":material/warning:")
            continue
        try:
            ex = timing.exit_check(idx.indicators(data[p["code"]]), buy_day, p["price"], p["mode"])
        except ValueError:
            st.warning(t["pos_err"].format(code=p["code"], day=day_name(buy_day)), icon=":material/warning:")
            continue
        hold = idx.MODES[p["mode"]]["hold"]
        action = ex["action"]
        if action == "hold" and now.date() == ex["deadline"] and phase != "closed":
            action = "hold_last"
        label, css, advice = t["act"][action]
        with st.container(border=True):
            st.markdown(stock_row(p["code"], (label, css)), unsafe_allow_html=True)
            rows = [(t["pos_price"], f"{num(p['price'])} · {p['lots']} lot · {t[p['mode']].strip('*')}"),
                    (t["stop"], num(ex["stop"]), "down"), (t["target"], num(ex["target"]), "up")]
            if ex["last"] is not None:
                rows.append((t["pnl"], f"{'+' if ex['pnl'] > 0 else ''}{pct(ex['pnl'], 2)} "
                                       f"(Rp {num(p['lots'] * idx.LOT * p['price'] * ex['pnl'] / 100)})",
                             "up" if ex["pnl"] > 0 else "down" if ex["pnl"] < 0 else ""))
            rows += [(t["held"], t["day_n"].format(n=ex["days"], m=hold)),
                     (t["deadline"], day_name(ex["deadline"]))]
            st.markdown(ui.ticket(rows), unsafe_allow_html=True)
            tv_line(p["code"], pos_tv_d, pos_tv_m)
            box = st.success if css == "up" else st.error if css == "down" else st.info
            box(f"**{label}** · " + advice.format(stop=num(ex["stop"]), target=num(ex["target"]), m=hold),
                icon=":material/campaign:")
            b1, b2 = st.columns(2)
            b1.link_button(t["open_stockbit"].format(code=p["code"]), f"https://stockbit.com/symbol/{p['code']}",
                           icon=":material/open_in_new:", width="stretch")
            with b2.popover(t["pos_delete"], icon=":material/delete:", width="stretch"):
                st.write(t["pos_confirm"].format(code=p["code"]))
                if st.button(t["pos_delete"], key=f"del{i}", type="primary"):
                    write_positions(positions[:i] + positions[i + 1:])
                    st.rerun()

# ---------- ML ----------
with tab_ml:
    st.markdown(t["ml_intro"])
    st.caption(t["ml_why"])
    c1, c2 = st.columns([1, 2])
    c1.metric(t["auc"], num(auc, 3), help=t["auc_help"], border=True)
    if has_edge:
        c2.success(t["ml_good"], icon=":material/verified:")
    else:
        c2.warning(t["ml_bad"], icon=":material/block:")
    # without a proven edge, the ranking goes behind the expander so beginners do not act on it
    details = st.expander(t["details"], icon=":material/science:")
    with st.container() if has_edge else details:
        st.subheader(t["top"], anchor=False)
        top = df.sort_values("ml_prob", ascending=False).head(10)[["code", "ml_prob", "signal", "close"]]
        st.dataframe(top, hide_index=True, width="stretch", column_config={
            "code": col_text["code"][0],
            "ml_prob": st.column_config.ProgressColumn(t["prob"], min_value=0, max_value=1, format="percent"),
            "signal": st.column_config.CheckboxColumn(col_text["signal"][0], help=col_text["signal"][1]),
            "close": st.column_config.NumberColumn(col_text["close"][0], format="localized"),
        })
    st.caption(t["foreign_ok"].format(n=foreign_days, used=t["foreign_used" if use_foreign else "foreign_wait"])
               if foreign_days else t["foreign_none"])
    with details:
        st.caption(t["ml_tech"])
        st.dataframe(wf, hide_index=True, width="stretch")

# ---------- all stocks ----------
def table(view):
    """Full data table with labelled, explained columns (advanced users)."""
    money = {"close", "entry", "stop", "target", "cost_rp", "max_loss_rp"}
    config = {}
    for k, (label, hlp) in col_text.items():
        if k == "ml_prob":
            config[k] = st.column_config.ProgressColumn(label, help=hlp, min_value=0, max_value=1, format="percent")
        elif k == "signal":
            config[k] = st.column_config.CheckboxColumn(label, help=hlp)
        elif k in money:
            config[k] = st.column_config.NumberColumn(label, help=hlp, format="localized")
        else:
            config[k] = st.column_config.Column(label, help=hlp)
    config["code"] = st.column_config.TextColumn(col_text["code"][0], help=col_text["code"][1], pinned=True)
    for k in cond_keys:
        config[k] = st.column_config.CheckboxColumn(cond_text[k].split(":")[0], help=cond_text[k])
    order = ["code", "signal", "score", "ml_prob", "close", "chg%", "entry", "stop", "target", "loss%", "lots",
             "cost_rp", "max_loss_rp", *cond_keys, "rsi", "value20_bn", "bt_trades", "bt_win%", "bt_avg%"]
    st.dataframe(view, hide_index=True, width="stretch", column_config=config, column_order=order)


with tab_all:
    st.caption(t["all_intro"])
    view = df[df["signal"]] if st.toggle(t["only_signal"]) else df
    st.markdown("".join(stock_row(r["code"], (t["conds"].format(a=r["score"], b=len(cond_keys)),
                                              "up" if r["signal"] else "flat"))
                        for _, r in view.iterrows()), unsafe_allow_html=True)
    with st.expander(t["full_table"], icon=":material/table_view:"):
        table(view)
    st.caption(t["footer"])

# ---------- guide ----------
with tab_guide:
    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        st.subheader(t["guide_steps_title"], anchor=False)
        st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(t["guide_steps"], 1)))
        st.subheader(t["guide_terms_title"], anchor=False)
        for term, meaning in GLOSSARY[lang]:
            st.markdown(f"**{term}**: {meaning}")
    with g2:
        with st.container(border=True):
            st.subheader(t["hours_title"], anchor=False)
            st.markdown("  \n".join(f":material/schedule: {h}" for h in t["hours"]))
        with st.container(border=True):
            st.subheader(t["guide_risk_title"], anchor=False)
            st.markdown("  \n".join(f":material/error_outline: {s}" for s in t["guide_risk"]))

st.divider()
st.caption(t["disclaimer"])
