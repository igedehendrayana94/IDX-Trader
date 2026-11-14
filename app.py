from pathlib import Path

import streamlit as st

import idx
import ml
from texts import COLS, COND, GLOSSARY, T

st.set_page_config(page_title="IDX Trader", page_icon=":material/candlestick_chart:", layout="wide")

FOREIGN_DIR = Path(__file__).parent / "data" / "foreign"
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
    capital = st.number_input(t["capital"], min_value=1_000_000, value=10_000_000, step=1_000_000,
                              help=t["capital_help"])
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
    return idx.fetch(list(code_list), period="5y")


@st.cache_data(ttl=3600, show_spinner=False)
def load_ihsg():
    return idx.fetch_ihsg(period="5y")


@st.cache_data(ttl=3600, show_spinner=False)
def load_foreign():
    return idx.load_foreign(FOREIGN_DIR)


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

st.caption(f":material/event: {t['kpi_date']} {df['date'].max().strftime('%d-%m-%Y')}")
buys = df[df["signal"] & (df["lots"] > 0)]
ihsg_chg = ihsg["Close"].pct_change().iloc[-1] * 100
k1, k2, k3 = st.columns(3, border=True)
k1.metric(t["kpi_buys"], len(buys))
k2.metric(t["kpi_ihsg"], num(ihsg["Close"].iloc[-1]), pct(ihsg_chg, 2))
k3.metric(t["kpi_ml"], t["ml_on"] if has_edge else t["ml_off"], help=t["auc_help"])

tab_rec, tab_ml, tab_all, tab_guide = st.tabs([
    f":material/thumb_up: {t['tab_rec']}", f":material/psychology: {t['tab_ml']}",
    f":material/table_view: {t['tab_all']}", f":material/school: {t['tab_guide']}",
])

# ---------- recommendations ----------
with tab_rec:
    st.markdown(t["rec_intro"].format(n=len(cond_keys), mode=t[mode]))
    for _, r in buys.iterrows():
        with st.container(border=True):
            h1, h2 = st.columns([3, 1], vertical_alignment="center")
            h1.subheader(r["code"], anchor=False)
            h1.badge(t["buy"], icon=":material/trending_up:", color="green")
            h2.link_button(t["open_stockbit"].format(code=r["code"]), f"https://stockbit.com/symbol/{r['code']}",
                           icon=":material/open_in_new:", type="primary", width="stretch")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(t["entry"], num(r["entry"]))
            m2.metric(t["stop"], num(r["stop"]), pct(r["loss%"], 2), help=t["stop_help"])
            m3.metric(t["target"], num(r["target"]), "+" + pct((r["target"] / r["entry"] - 1) * 100, 2),
                      help=t["target_help"])
            m4.metric(t["lots"], num(r["lots"]), help=t["lots_help"])
            st.markdown(t["money"].format(cost=num(r["cost_rp"]), maxloss=num(r["max_loss_rp"]),
                                          pct=pct(r["max_loss_rp"] / capital * 100, 1)))
            st.markdown(f"**{t['why']}**")
            st.markdown("  \n".join(f":material/check_circle: {cond_text[k]}" for k in cond_keys))
            st.markdown(t["ml_line"].format(prob=pct(r["ml_prob"] * 100), base=pct(base_win))
                        if has_edge else t["ml_skip"])
            st.caption(t["history"].format(n=r["bt_trades"], win=pct(r["bt_win%"]), avg=pct(r["bt_avg%"], 2))
                       if r["bt_trades"] else t["history_none"])
            if r["bt_trades"] and r["bt_avg%"] < 0:
                st.warning(t["history_bad"], icon=":material/warning:")

    if buys.empty:
        st.info(f"**{t['none_title']}** {t['none_body']}", icon=":material/hourglass_empty:")
    no_money = df[df["signal"] & (df["lots"] == 0)]
    if len(no_money):
        st.warning(t["zero_lots"].format(codes=", ".join(no_money["code"])), icon=":material/savings:")

    near = df[~df["signal"] & (df["score"] == len(cond_keys) - 1)].head(6)
    if len(near):
        st.subheader(t["near_title"], anchor=False)
        st.caption(t["near_intro"])
        cols = st.columns(3)
        for i, (_, r) in enumerate(near.iterrows()):
            miss = next(k for k in cond_keys if not r[k])
            with cols[i % 3].container(border=True):
                st.markdown(f"**{r['code']}** · {num(r['close'])} ({'+' if r['chg%'] > 0 else ''}{pct(r['chg%'], 2)})")
                st.caption(f":material/radio_button_unchecked: {t['near_missing'].format(cond=cond_text[miss])}")

# ---------- ML ----------
with tab_ml:
    st.markdown(t["ml_intro"])
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
with tab_all:
    st.caption(t["all_intro"])
    view = df[df["signal"]] if st.toggle(t["only_signal"]) else df
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
            st.subheader(t["guide_risk_title"], anchor=False)
            st.markdown("  \n".join(f":material/error_outline: {s}" for s in t["guide_risk"]))

st.divider()
st.caption(t["disclaimer"])
