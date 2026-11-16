import re
import io
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import idx
import journal
import ml
import news
import orb
import report
import risk
import timing
import ui
from texts import COLS, COND, GLOSSARY, T

st.set_page_config(page_title="IDX Trader", page_icon=":material/candlestick_chart:", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
FOREIGN_DIR = DATA_DIR / "foreign"
POSITIONS = DATA_DIR / "positions.json"
JOURNAL = DATA_DIR / "journal.json"
NEWS_DIR = DATA_DIR / "news"
FOREIGN_MIN_DAYS = 60  # fewer days = feature mostly empty in training, no point using it

# ---------- sidebar: only the choices a beginner must make are visible ----------
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


def day_name(d):
    return f"{t['days'][d.weekday()]}, {d.strftime('%d-%m-%Y')}"


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
    risk_pct = st.slider(t["risk_pct"], 0.5, 2.0, 1.0, 0.5, help=t["risk_help"], format="%.1f%%")
    with st.expander(t["advanced"], icon=":material/tune:"):
        max_alloc = st.slider(t["alloc"], 5, 100, 25, 5, help=t["alloc_help"]) / 100
        daily_loss = st.slider(t["daily_loss"], 1.0, 5.0, 3.0, 0.5, format="%.1f%%")
        max_open = st.number_input(t["max_open"], 1, 10, 5)
        max_trades = st.number_input(t["max_trades"], 1, 10, 3)
        min_value = st.number_input(t["min_value"], min_value=0.0, value=5.0, step=1.0,
                                    help=t["min_value_help"]) * 1e9
        codes = st.text_area(t["universe"], " ".join(idx.UNIVERSE), height=160)
        use_ihsg = st.checkbox(t["use_ihsg"], value=True)
    refresh = st.button(t["refresh"], icon=":material/refresh:", width="stretch")
    st.caption(t["rules"].format(loss=pct(idx.MAX_LOSS * 100), buy=pct(idx.BUY_FEE * 100, 2),
                                 sell=pct(idx.SELL_FEE * 100, 2)))
limits = {**risk.DEFAULT_LIMITS, "risk_pct": risk_pct, "daily_loss_pct": daily_loss,
          "max_open": max_open, "max_trades_day": max_trades}


@st.cache_data(ttl=3600, show_spinner=False)
def load(code_list, day):  # day = cache key so the new closed bar shows right at 16:15, not up to 1h later
    now = datetime.now(timing.WIB)
    return {c: timing.drop_unfinished(d, now) for c, d in idx.fetch(list(code_list), period="5y").items()}


@st.cache_data(ttl=3600, show_spinner=False)
def load_ihsg(day):
    return timing.drop_unfinished(idx.fetch_ihsg(period="5y"), datetime.now(timing.WIB))


@st.cache_data(ttl=3600, show_spinner=False)
def load_foreign():
    return idx.load_foreign(FOREIGN_DIR)


@st.cache_data(ttl=300, show_spinner=False)
def load_live(code_list):
    """Today's unfinished daily bar per code and IHSG (yfinance, ~15 min late): prices on screen only,
    signals keep using closed days."""
    bars = idx.fetch(list(code_list), period="6mo")  # fetch needs >= 60 bars
    try:
        bars["IHSG"] = idx.fetch_ihsg(period="5d")
    except Exception:  # Yahoo hiccup: header falls back to the last close
        pass
    now = datetime.now(timing.WIB)
    return {c: d.iloc[-1:] for c, d in bars.items() if len(d) and d.index[-1].date() == now.date()}, now


@st.cache_data(ttl=300, show_spinner=False)
def load_tv(codes, interval):
    return idx.tv_ratings(list(codes), interval)


@st.cache_data(ttl=300, show_spinner=False)
def load_intraday(codes):
    return orb.fetch_intraday(list(codes))


@st.cache_data(ttl=3600, show_spinner=False)
def load_timemachine(codes, today):
    bars = load_intraday(codes)
    return {c: orb.timemachine(b, today) for c, b in bars.items()}


@st.cache_data(ttl=1800, show_spinner=False)
def load_news(code, today):
    items = news.fetch(code)
    news.save(items, NEWS_DIR, today)  # archive so the keyword score can be tested once months of headlines exist
    return items


@st.cache_data(ttl=3600, show_spinner=False)
def train_bsjp(code_list, day, use_ihsg, use_foreign):
    p = ml.dataset(load(code_list, day), "bsjp", ihsg=load_ihsg(day) if use_ihsg else None,
                   foreign=load_foreign() if use_foreign else None)
    o = ml.oos(p, "bsjp")
    move = ((o["ret"] + 1) * (1 + idx.BUY_FEE) / (1 - idx.SELL_FEE) - 1) * 100  # next open vs close, before fees
    rng = {r: {"n": int(m.sum()), "med": move[m].median(), "p25": move[m].quantile(0.25),
               "p75": move[m].quantile(0.75), "win": (o["ret"][m] > 0).mean() * 100}
           for r in (1, 2, 3) for m in [o["rank"] == r]}
    return ml.summary(o), ml.fit(p), rng


@st.cache_data(ttl=300, show_spinner=False)
def bsjp_probs(code_list, day, use_ihsg, use_foreign, live_at):
    """P(buy at today's close, sell next open ends in profit) from today's unfinished (delayed) bar.
    live_at is only the cache key: new delayed prices -> new probabilities."""
    m = train_bsjp(code_list, day, use_ihsg, use_foreign)[1]
    recent = {c: with_live(c, data[c]).tail(300) for c in code_list if c in data}  # 300 bars cover every feature
    p = ml.dataset(recent, "bsjp", ihsg=with_live("IHSG", ihsg) if use_ihsg else None,
                   foreign=load_foreign() if use_foreign else None)
    return ml.predict_latest(p, m)


@st.cache_data(ttl=3600, show_spinner=False)
def bsjp_history(code_list, day):
    return {c: idx.bsjp_backtest(idx.indicators(d)) for c, d in load(code_list, day).items()}


@st.cache_data(ttl=3600, show_spinner=False)
def train(code_list, day, mode, use_ihsg, use_foreign):
    p = ml.dataset(load(code_list, day), mode, ihsg=load_ihsg(day) if use_ihsg else None,
                   foreign=load_foreign() if use_foreign else None)
    return ml.walk_forward(p, mode), ml.predict_latest(p)


if refresh:
    for f in (load, load_ihsg, load_live, bsjp_history, train_bsjp, bsjp_probs, load_news, load_foreign, load_tv, load_intraday, load_timemachine, train):
        f.clear()

# ---------- data ----------
code_list = tuple(sorted({c.strip().upper() for c in codes.split() if c.strip()}))
now = datetime.now(timing.WIB)
day = (now.date(), now.time() >= timing.DATA_READY)
with st.spinner(t["downloading"]):
    data, ihsg = load(code_list, day), load_ihsg(day)
    live, live_at = load_live(code_list)
reg = risk.regime_series(data, ihsg).iloc[-1] if data else None
light = reg["light"] if reg is not None else "yellow"
factor = 0.5 if light == "yellow" else 1.0  # red keeps full plan for learning; the risk gate blocks the buy
df = idx.screen(data, mode, capital, max_alloc, min_value, risk_pct, factor)
positions, trades = journal.load(POSITIONS), journal.load(JOURNAL)
foreign_days = load_foreign()["date"].nunique()
use_foreign = foreign_days >= FOREIGN_MIN_DAYS
if not df.empty:
    with st.spinner(t["training"]):
        wf, prob = train(code_list, day, mode, use_ihsg, use_foreign)
    df.insert(4, "ml_prob", df["code"].map(prob).round(3))
    auc = wf["auc"].mean() if len(wf) else 0.5
    base_win = wf["base_win%"].mean() if len(wf) else float("nan")
    has_edge = auc >= 0.53  # shortcut: fixed AUC bar, replace with a significance test if folds grow
cond_keys = list(idx.conditions(idx.indicators(next(iter(data.values()))), mode).columns) if data else []

# ---------- header: the answer first ----------
st.title("IDX Trader")
st.caption(t["subtitle"])
missing = set(code_list) - set(data)
if not data:
    load.clear()  # Yahoo failed outright; don't serve the empty result for the full TTL
if missing:
    st.warning(t["no_data"] + " ".join(sorted(missing)), icon=":material/warning:")
if df.empty:
    st.info(t["no_liquid"], icon=":material/info:")
    st.stop()

phase, when = timing.market_status(now)
MARKET_OPEN = ("pre_open", "session1", "break", "session2", "pre_close")
when_txt = (t["opens"].format(when=f"{day_name(when)} {when:%H:%M}") if phase == "closed"
            else t["until"].format(when=f"{when:%H:%M}"))
st.caption(f":material/event: {t['kpi_date']} {df['date'].max().strftime('%d-%m-%Y')}  ·  "
           f":material/schedule: **{t['phase'][phase]}** · {when_txt} WIB"
           + (f"  ·  :material/update: {t['live_at'].format(time=f'{live_at:%H:%M}')}" if live else ""))
st.session_state["ran_at"] = now


@st.fragment(run_every=300 if phase in MARKET_OPEN else None)
def auto_refresh():
    """Rerun the whole page every 5 min while the market is open so prices stay current."""
    if (datetime.now(timing.WIB) - st.session_state["ran_at"]).total_seconds() >= 290:
        st.rerun(scope="app")


auto_refresh()
buys = df[df["signal"] & (df["lots"] > 0)]
if has_edge:
    buys = buys.sort_values("ml_prob", ascending=False)


def tv_line(code, tv_d, tv_m):
    """One-line TradingView second opinion, or nothing when TradingView has no data."""
    d, m = tv_d.get(code), tv_m.get(code)
    if not d:
        return
    st.markdown(t["tv_line"].format(d=t["tv_rec"][d["rec"]], m=t["tv_rec"][m["rec"]] if m else "-",
                                    b=d["buy"], n=d["neutral"], s=d["sell"]), help=t["tv_note"])


def with_live(code, df):
    """Closed daily bars plus today's unfinished bar when there is one."""
    bar = live.get(code)
    return df if bar is None or bar.index[-1] <= df.index[-1] else pd.concat([df, bar])


def stock_row(code, chip=None):
    """Watchlist row from price history: latest price, change vs previous close, 30-day sparkline."""
    c = with_live(code, data[code] if code in data else ihsg)["Close"]
    name = t["ihsg_name"] if code == "IHSG" else idx.NAMES.get(code, "")
    return ui.row(code, name, c.tail(30), c.iloc[-1], c.iloc[-1] - c.iloc[-2],
                  (c.iloc[-1] / c.iloc[-2] - 1) * 100, num, chip)


def news_block(code):
    """Headlines of the last 7 days with keyword sentiment; returns the number of red-flag headlines."""
    s = news.summary(load_news(code, now.date()))
    if not s["n"]:
        st.caption(f":material/newspaper: {t['news_none']}")
        return 0
    st.markdown(f":material/newspaper: {t['news_line'].format(n=s['n'], pos=s['pos'], neg=s['neg'])}")
    for i in s["red"][:2]:
        st.error(t["news_red"].format(title=esc(i["title"])), icon=":material/report:")
    with st.expander(t["news_list"]):
        icon = {1: ":material/trending_up:", -1: ":material/trending_down:", 0: ":material/remove:"}
        st.markdown("  \n".join(f"{icon[i['score']]} [{esc(i['title'])}]({i['link']}) · {i['time'][:10]}"
                                for i in load_news(code, now.date())[:8]))
        st.caption(t["news_note"])
    return len(s["red"])


def esc(text):
    """Headline text safe for st.markdown (no links, LaTeX or emphasis from the title itself)."""
    return re.sub(r"([\\`*_\[\]$<>#])", r"\\\1", text)


def show_gate(checks, with_window=False):
    """Render the pre-trade checklist; returns True when every check passes."""
    fmt = {
        "regime": lambda d: {"light": t["light"][d["light"]]},
        "rr": lambda d: {"rr": num(d["rr"], 1), "min": num(d["min"], 1)},
        "cash": lambda d: {"need": num(d["need"]), "free": num(d["free"])},
        "daily_loss": lambda d: {"loss": num(d["loss"]), "max": num(d["max"])},
        "streak": lambda d: {"n": d["n"], "until": day_name(d["until"]) if d["until"] else ""},
    }
    lines = []
    for key, ok, d in checks:
        if key == "window" and not with_window:
            continue
        text = t["gate"][key][0 if ok else 1].format(**fmt.get(key, lambda x: x)(d))
        lines.append(f"{':material/check_circle:' if ok else ':material/cancel:'} {text}")
    ok_all = risk.passed(checks)
    st.markdown(f"**{t['gate_title']}**")
    st.markdown("  \n".join(lines))
    (st.success if ok_all else st.error)(t["gate_pass"] if ok_all else t["gate_block"],
                                         icon=":material/verified_user:" if ok_all else ":material/block:")
    return ok_all


def add_position(code, pos_mode, price, lots, stop, target, key):
    if st.button(t["bought"], key=key, icon=":material/add_task:", width="stretch"):
        positions.append({"code": code, "mode": pos_mode, "date": now.date().isoformat(), "price": float(price),
                          "lots": int(lots), "stop": float(stop), "target": float(target)})
        journal.save(POSITIONS, positions)
        st.toast(t["bought_ok"], icon=":material/check:")
        st.rerun(scope="app")  # positions and risk checks change everywhere


st.html(ui.CSS)
st.markdown(stock_row("IHSG"), unsafe_allow_html=True)
st.markdown(ui.stats([(t["kpi_regime"], t["light"][light]), (t["kpi_buys"], str(len(buys))),
                      (t["kpi_ml"], t["ml_on"] if has_edge else t["ml_off"])]), unsafe_allow_html=True)
if reg is not None:
    reasons = [t["reg_ihsg"][0 if reg["ihsg_up"] else 1], t["reg_ema"][0 if reg["ema_rising"] else 1],
               t["reg_breadth"].format(x=pct(reg["breadth"])), t["reg_dist"].format(n=int(reg["dist_days"]))]
    box = {"green": st.success, "yellow": st.warning, "red": st.error}[light]
    box(f"**{t['regime_title'].format(light=t['light'][light])}** · {t['regime_do'][light]}  \n"
        + " · ".join(reasons), icon=":material/traffic:")
    st.caption(t["reg_dist_help"])

tab_rec, tab_orb, tab_pos, tab_jr, tab_acc, tab_all, tab_guide = st.tabs([
    f":material/thumb_up: {t['tab_rec']}", f":material/bolt: {t['tab_orb']}", f":material/work: {t['tab_pos']}",
    f":material/menu_book: {t['tab_journal']}", f":material/fact_check: {t['tab_acc']}",
    f":material/format_list_bulleted: {t['tab_all']}", f":material/school: {t['tab_guide']}",
], on_change="rerun", key="main_tab")  # rerun -> tab.open, so Akurasi runs only when open

# ---------- recommendations (swing / daily) ----------
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
            red = news_block(r["code"])
            ok = show_gate(risk.gate(r["entry"], r["stop"], r["target"], r["lots"], capital, light, positions,
                                     trades, now.date(), limits, news_red=red))
            st.link_button(t["cta_buy"].format(code=r["code"]), f"https://stockbit.com/symbol/{r['code']}",
                           icon=":material/open_in_new:", type="primary", width="stretch", disabled=not ok)
            if ok:
                add_position(r["code"], mode, r["entry"], r["lots"], r["stop"], r["target"], f"buy_{r['code']}")

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

    with st.expander(t["ml_rel_title"].format(mode=t[mode]), icon=":material/psychology:"):
        st.markdown(t["ml_intro"])
        st.caption(t["ml_why"])
        c1, c2 = st.columns([1, 2])
        c1.metric(t["auc"], num(auc, 3), help=t["auc_help"], border=True)
        (c2.success if has_edge else c2.warning)(t["ml_good"] if has_edge else t["ml_bad"],
                                                 icon=":material/verified:" if has_edge else ":material/block:")
        st.caption(t["foreign_ok"].format(n=foreign_days, used=t["foreign_used" if use_foreign else "foreign_wait"])
                   if foreign_days else t["foreign_none"])
        st.caption(t["ml_tech"])
        st.dataframe(wf, hide_index=True, width="stretch")


# ---------- day trading: opening range breakout ----------
ORB_ORDER = ["open", "waiting", "forming", "target", "stop", "time", "expired", "no_range"]
ORB_CSS = {"open": "up", "target": "up", "stop": "down", "time": "flat"}


@st.fragment(run_every=300 if phase in MARKET_OPEN else None)
def orb_view():
    st.markdown(t["orb_intro"])
    st.caption(f":material/schedule: {t['orb_delay']}")
    st.caption(f":material/psychology: {t['orb_ml']}")
    liquid = tuple(df["code"])
    bars = load_intraday(liquid)
    if not bars:
        st.info(t["no_data"] + " 5m", icon=":material/info:")
        return
    tm = load_timemachine(liquid, now.date())
    done = {c: s for c, s in tm.items() if s["trades"]}
    n = sum(s["trades"] for s in done.values())
    if n:
        win = sum(s["win%"] * s["trades"] for s in done.values()) / n
        avg = sum(s["avg%"] * s["trades"] for s in done.values()) / n
        st.subheader(t["orb_tm_title"], anchor=False)
        (st.success if avg > 0 else st.error)(
            t["orb_tm"].format(trades=n, stocks=len(done), win=pct(win), avg=pct(avg, 2)) + " "
            + (t["orb_tm_good"] if avg > 0 else t["orb_tm_bad"]),
            icon=":material/history:")
        with st.expander(t["orb_table"], icon=":material/table_view:"):
            st.dataframe(
                [{"code": c, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}}
                 for c, s in sorted(done.items(), key=lambda x: -x[1]["avg%"])],
                hide_index=True, width="stretch")

    latest = max(b.index[-1].date() for b in bars.values())
    live = latest == now.date() and phase != "closed"
    st.subheader(t["orb_live"] if live else t["orb_last"].format(day=day_name(latest)), anchor=False)
    results = {}
    for c, b in bars.items():
        g = b[b.index.date == latest]
        if len(g):
            results[c] = (g, orb.day(g, now if live else None))
    html = ""
    for c, (g, res) in sorted(results.items(), key=lambda x: ORB_ORDER.index(x[1][1]["status"])):
        prev = data[c]["Close"][data[c].index.date < latest]
        last = float(g["Close"].iloc[-1])
        chip = t["orb_status"][res["status"]]
        if "ret" in res:
            chip += f" {'+' if res['ret'] > 0 else ''}{pct(res['ret'] * 100, 2)}"
        html += ui.row(c, idx.NAMES.get(c, ""), g["Close"], last, last - prev.iloc[-1],
                       (last / prev.iloc[-1] - 1) * 100, num, (chip, ORB_CSS.get(res["status"], "flat")))
        if live and res["status"] == "open":
            st.markdown(html, unsafe_allow_html=True)
            html = ""
            orb_card(c, res)
    st.markdown(html, unsafe_allow_html=True)


def orb_card(code, res):
    entry, stop, target = res["entry"], res["stop"], res["target"]
    lots = risk.size_lots(capital, risk_pct, entry, stop, max_alloc, factor)
    with st.container(border=True):
        st.markdown(ui.ticket([
            (t["orb_range"], f"{num(res['lo'])} – {num(res['hi'])}"),
            (t["orb_trigger"], f"{res['trigger_time']:%H:%M} WIB"),
            (t["entry"], num(entry)),
            (t["stop"], f"{num(stop)} ({pct((stop / entry - 1) * 100, 2)})", "down"),
            (t["target"], f"{num(target)} (+{pct((target / entry - 1) * 100, 2)})", "up"),
            (t["lots"], f"{num(lots)} lot"),
            (t["total"], f"Rp {num(lots * idx.LOT * entry * (1 + idx.BUY_FEE))}"),
            (t["plan_exit"], t["orb_exit"], "down"),
        ]), unsafe_allow_html=True)
        chased = (res["last"] - entry) / (entry - stop)
        if chased > 0.5:
            st.warning(t["orb_chase"].format(r=num(chased, 1)), icon=":material/directions_run:")
        red = news_block(code)
        ok = show_gate(risk.gate(entry, stop, target, lots, capital, light, positions, trades, now.date(), limits,
                                 window_open=now.time() < orb.ENTRY_CUTOFF, news_red=red), with_window=True) \
            and chased <= 0.5
        st.link_button(t["cta_buy"].format(code=code), f"https://stockbit.com/symbol/{code}",
                       icon=":material/open_in_new:", type="primary", width="stretch", disabled=not ok)
        if ok:
            add_position(code, "orb", entry, lots, stop, target, f"orb_{code}")


BSJP_FROM = time(15, 0)  # earlier the daily bar is too unfinished to call a signal
BSJP_UNTIL = time(16, 15)  # end of post-trading, where trades happen only at the closing price


def bsjp_view():
    st.markdown(t["bsjp_intro"])
    st.caption(f":material/schedule: {t['bsjp_delay']}")
    hist = bsjp_history(code_list, day)
    allh = pd.concat(hist.values()) if hist else pd.DataFrame(columns=["bsjp", "morning"])
    if len(allh):
        avg = allh["bsjp"].mean() * 100
        (st.success if avg > 0 else st.warning)(
            t["bsjp_hist"].format(n=len(allh), avg=pct(avg, 2), win=pct((allh["bsjp"] > 0).mean() * 100),
                                  morning=pct(allh["morning"].mean() * 100, 2)), icon=":material/history:")
    wf_b = train_bsjp(code_list, day, use_ihsg, use_foreign)[0]
    edge = len(wf_b) and wf_b["auc"].mean() >= 0.53
    if edge:
        st.success(t["bsjp_ml_hist"].format(auc=num(wf_b["auc"].mean(), 2), top1=pct(wf_b["top1_avg%"].mean(), 2),
                                            top3=pct(wf_b["top3_avg%"].mean(), 2), base=pct(wf_b["base_avg%"].mean(), 2),
                                            last=pct(wf_b["top1_avg%"].iloc[-1], 2)), icon=":material/psychology:")
    else:
        st.caption(f":material/psychology: {t['bsjp_ml_none']}")
    window = (phase in ("session2", "pre_close") and now.time() >= BSJP_FROM) or \
        (timing.is_trading_day(now.date()) and time(16, 0) <= now.time() < BSJP_UNTIL)
    if not window:
        st.info(t["bsjp_wait"], icon=":material/schedule:")
    st.subheader(t["bsjp_list"], anchor=False)
    today = [c for c in df["code"] if c in live]  # liquid stocks with a bar for today (delayed, unfinished)
    frames = {c: idx.indicators(with_live(c, data[c])) for c in today}
    rule = {c for c, d in frames.items() if idx.conditions(d, "daily").iloc[-1].all()}
    rng = train_bsjp(code_list, day, use_ihsg, use_foreign)[2]
    if edge and today:
        prob = bsjp_probs(code_list, day, use_ihsg, use_foreign, live_at)
        picks = list(prob.reindex(today).dropna().sort_values(ascending=False).head(3).items())
        st.caption(t["bsjp_ml_pick"])
    else:
        picks = [(c, None) for c in rule]
    if not picks:
        st.info(t["bsjp_none"], icon=":material/hourglass_empty:")
    for rank, (c, pr) in enumerate(picks, 1):
        bsjp_card(c, frames[c], hist.get(c), window, pr, rank, c in rule, rng.get(rank) if pr is not None else None)


def bsjp_card(code, d, hist, window, prob=None, rank=None, rule_ok=True, rng=None):
    last = float(d["Close"].iloc[-1])
    # one tick of room so the auction order fills; the auction still charges the closing price, not the limit.
    # The overnight edge is about one tick, so a close above this means skip, not chase.
    max_px = last + idx.tick(last)
    stop, target, lots = idx.plan(max_px, float(d["atr"].iloc[-1]), "daily", capital, max_alloc, risk_pct, factor)
    signed = lambda x: ("+" if x > 0 else "") + pct(x, 2)  # noqa: E731
    rows = [(t["bsjp_now"], num(last)), (t["bsjp_max"], num(max_px)),
            (t["bsjp_buy"], t["bsjp_buy_v"].format(max=num(max_px))),
            (t["bsjp_sell"], t["bsjp_sell_v"].format(day=day_name(timing.next_trading_day(now.date()))))]
    if rng and rng["n"]:
        rows.append((t["bsjp_range"], t["bsjp_range_v"].format(med=signed(rng["med"]), p25=signed(rng["p25"]),
                                                               p75=signed(rng["p75"]))))
    rows += [(t["stop"], f"{num(stop)} ({pct((stop / max_px - 1) * 100, 2)})", "down"),
             (t["lots"], f"{num(lots)} lot"), (t["total"], f"Rp {num(lots * idx.LOT * max_px * (1 + idx.BUY_FEE))}")]
    if hist is not None and len(hist):
        rows.append((t["bsjp_stock_hist"], t["bsjp_stock_hist_v"].format(n=len(hist),
                                                                           avg=pct(hist["bsjp"].mean() * 100, 2))))
    with st.container(border=True):
        chip = t["bsjp_chip"] if prob is None else t["bsjp_chip_ml"].format(rank=rank, prob=pct(prob * 100))
        st.markdown(stock_row(code, (chip, "up")), unsafe_allow_html=True)
        st.markdown(ui.ticket(rows), unsafe_allow_html=True)
        st.caption(t["bsjp_how"].format(max=num(max_px)))
        if rng and rng["n"]:
            st.caption(t["bsjp_range_note"].format(n=num(rng["n"]), rank=rank, win=pct(rng["win"])))
        st.markdown(t["bsjp_rule_yes"] if rule_ok else t["bsjp_rule_no"])
        st.caption(t["bsjp_gap"])
        red = news_block(code)
        checks = [("window_bsjp" if k == "window" else k, ok, x) for k, ok, x in
                  risk.gate(max_px, stop, target, lots, capital, light, positions, trades, now.date(), limits,
                            window_open=window, news_red=red)]
        ok = show_gate(checks)
        st.link_button(t["cta_buy"].format(code=code), f"https://stockbit.com/symbol/{code}",
                       icon=":material/open_in_new:", type="primary", width="stretch", disabled=not ok)
        if ok:
            add_position(code, "bsjp", max_px, lots, stop, target, f"bsjp_{code}")


with tab_orb:
    how = st.segmented_control(t["dt_when"], ["orb", "bsjp"], default="orb", required=True,
                               format_func=lambda k: t["dt_opt"][k], key="dt_when")
    if how == "orb":
        orb_view()
    else:
        bsjp_view()

# ---------- my positions ----------
MODES_ALL = ["swing", "daily", "orb", "bsjp"]
EXIT_REASON = {"sell_stop": "stop", "sell_target": "target", "sell_time": "time"}

with tab_pos:
    with st.expander(t["add_pos"], icon=":material/add:", expanded=not positions):
        with st.form("add_position", clear_on_submit=True, border=False):
            f1, f2 = st.columns(2)
            p_code = f1.selectbox(t["pos_code"], sorted(data))
            p_mode = f2.radio(t["pos_mode"], MODES_ALL, format_func=lambda m: t[m], horizontal=True,
                              index=MODES_ALL.index(mode))
            f3, f4, f5 = st.columns(3)
            p_date = f3.date_input(t["pos_date"], value=now.date(), max_value=now.date(), format="DD/MM/YYYY")
            p_price = f4.number_input(t["pos_price"], min_value=0, step=5)
            p_lots = f5.number_input(t["pos_lots"], min_value=0, step=1)
            if st.form_submit_button(t["pos_save"], icon=":material/save:", type="primary"):
                if p_price > 0 and p_lots >= 1 and p_date <= now.date():
                    positions.append({"code": p_code, "mode": p_mode, "date": p_date.isoformat(),
                                      "price": float(p_price), "lots": int(p_lots)})
                    journal.save(POSITIONS, positions)
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
            ex = timing.exit_check(idx.indicators(with_live(p["code"], data[p["code"]])), buy_day, p["price"], p["mode"],
                                   p.get("stop"), p.get("target"))
        except ValueError:
            st.warning(t["pos_err"].format(code=p["code"], day=day_name(buy_day)), icon=":material/warning:")
            continue
        hold = timing.hold_days(p["mode"])
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
            b1, b2, b3 = st.columns(3)
            b1.link_button(t["open_stockbit"].format(code=p["code"]), f"https://stockbit.com/symbol/{p['code']}",
                           icon=":material/open_in_new:", width="stretch")
            with b2.popover(t["close_pos"], icon=":material/sell:", width="stretch"):
                x_price = st.number_input(t["exit_price"], min_value=1, step=5, key=f"xp{i}",
                                          value=int(ex["last"] or p["price"]))
                x_date = st.date_input(t["exit_date"], value=now.date(), min_value=buy_day, max_value=now.date(),
                                       format="DD/MM/YYYY", key=f"xd{i}")
                reasons = list(t["reasons"])
                x_reason = st.selectbox(t["exit_reason"], reasons, format_func=lambda k: t["reasons"][k], key=f"xr{i}",
                                        index=reasons.index(EXIT_REASON.get(ex["action"], "manual")))
                if st.button(t["close_pos"], key=f"close{i}", type="primary"):
                    trades.append(journal.close(p, float(x_price), x_date, x_reason, ex["stop"]))
                    journal.save(JOURNAL, trades)
                    journal.save(POSITIONS, positions[:i] + positions[i + 1:])
                    st.toast(t["close_ok"], icon=":material/check:")
                    st.rerun()
            with b3.popover(t["pos_delete"], icon=":material/delete:", width="stretch"):
                st.write(t["pos_confirm"].format(code=p["code"]))
                if st.button(t["pos_delete"], key=f"del{i}", type="primary"):
                    journal.save(POSITIONS, positions[:i] + positions[i + 1:])
                    st.rerun()

# ---------- journal ----------
with tab_jr:
    s = journal.stats(trades)
    if not s:
        st.info(t["j_none"], icon=":material/info:")
    else:
        m = st.columns(3, border=True)
        m[0].metric(t["j_trades"], s["n"])
        m[1].metric(t["j_win"], pct(s["win%"]))
        m[2].metric(t["j_total"], f"Rp {num(s['total'])}")
        m = st.columns(3, border=True)
        m[0].metric(t["j_exp"], f"Rp {num(s['expectancy'])}")
        m[1].metric(t["j_pf"], num(s["profit_factor"], 2) if s["profit_factor"] is not None else "-", help=t["j_pf_help"])
        m[2].metric(t["j_r"], num(s["avg_r"], 2) if s["avg_r"] is not None else "-", help=t["j_r_help"])
        for note in journal.coach(trades, s):
            (st.success if note == "positive" else st.info if note == "few_trades" else st.warning)(
                t["coach"][note], icon=":material/sports:")
        st.subheader(t["j_weekly"], anchor=False)
        st.dataframe(journal.weekly(trades), hide_index=True, width="stretch", column_config={
            "week": t["j_week"], "trades": t["j_trades"],
            "win": st.column_config.NumberColumn(t["j_win"], format="%.0f%%"),
            "pnl_rp": st.column_config.NumberColumn(t["j_pnl"], format="localized"),
        })
        st.subheader(t["j_list"], anchor=False)
        st.dataframe(sorted(trades, key=lambda j: j["exit_date"], reverse=True), hide_index=True, width="stretch")

# ---------- accuracy: what the app recommended vs real prices ----------
@st.cache_data(ttl=3600, show_spinner=False)
def load_accuracy(first, last, day):
    """Point-in-time replay of first..last (see report.py); day = cache key for the closed data."""
    raw = {c: with_live(c, data[c]) for c in data}  # today's bar gives the latest BSJP sell price (next open)
    return report.replay(pd.Timestamp(first), pd.Timestamp(last), raw=raw, data=data, ihsg=ihsg)


ACC_PCT = ["Akurasi (untung/selesai)", "Prediksi ML rata-rata", "Rata-rata hasil bersih", "Semua saham (pembanding)"]


def acc_table(df):
    cfg = {c: st.column_config.NumberColumn(c, format="percent") for c in ACC_PCT}
    cfg["AUC periode"] = st.column_config.NumberColumn("AUC periode", format="%.2f", help=t["auc_help"])
    cfg["Total untung/rugi per lot (Rp)"] = st.column_config.NumberColumn("Total untung/rugi per lot (Rp)",
                                                                          format="localized")
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg)


def acc_view():
    st.markdown(t["acc_intro"])
    choice = st.segmented_control(t["acc_period"], ["month", "this_week", "last_week", "custom"], default="month",
                                  required=True, format_func=lambda k: t["acc_opt"][k], key="acc_period")
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    if choice == "this_week":
        first, last = monday, monday + timedelta(days=6)
    elif choice == "last_week":
        first, last = monday - timedelta(days=7), monday - timedelta(days=1)
    elif choice == "month":
        first, last = today.replace(day=1), (pd.Timestamp(today) + pd.offsets.MonthEnd(0)).date()
    else:
        picked = st.date_input(t["acc_dates"], value=(today.replace(day=1), today), max_value=today,
                               format="DD/MM/YYYY")
        if len(picked) != 2:
            st.info(t["acc_pick_end"], icon=":material/date_range:")
            return
        first, last = picked
    with st.spinner(t["acc_loading"]):
        bsjp, rek, info, scored = load_accuracy(first, last, day)
    st.caption(t["acc_caption"].format(first=f"{first:%d/%m/%Y}", last=f"{last:%d/%m/%Y}",
                                       data=f"{info['data_to']:%d/%m/%Y}"))
    if bsjp.empty and rek.empty:
        st.info(t["acc_empty"], icon=":material/hourglass_empty:")
        return
    summary = report.summarize(bsjp, rek, scored)
    acc_table(summary.drop(columns="Minggu"))
    if summary["Selesai"].max() < 30:
        st.warning(t["acc_small"], icon=":material/science:")
    st.info(t["acc_how"], icon=":material/help:")
    if (last - first).days > 6:
        st.subheader(t["acc_weekly"], anchor=False)
        acc_table(report.summarize(bsjp, rek, scored, by_week=True))
    with st.expander(t["acc_bsjp_rows"].format(n=len(bsjp)), icon=":material/nightlight:"):
        st.dataframe(bsjp, hide_index=True, width="stretch")
    with st.expander(t["acc_rek_rows"].format(n=len(rek)), icon=":material/thumb_up:"):
        st.dataframe(rek, hide_index=True, width="stretch")
    buf = io.BytesIO()
    report.build(f"{first:%d/%m/%Y}–{last:%d/%m/%Y}", bsjp, rek, info).save(buf)
    c1, c2, c3 = st.columns(3)
    name = f"idx_trader_{first:%Y%m%d}_{last:%Y%m%d}"
    c1.download_button(t["acc_xlsx"], buf.getvalue(), f"{name}.xlsx", icon=":material/table_view:", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button(t["acc_csv_bsjp"], bsjp.to_csv(index=False), f"{name}_bsjp.csv", icon=":material/download:",
                       width="stretch", mime="text/csv")
    c3.download_button(t["acc_csv_rek"], rek.to_csv(index=False), f"{name}_rekomendasi.csv",
                       icon=":material/download:", width="stretch", mime="text/csv")


with tab_acc:
    if tab_acc.open:  # the replay is heavy (~30 s cold): run it only when this tab is selected
        acc_view()


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
