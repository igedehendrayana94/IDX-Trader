import streamlit as st

import idx

st.set_page_config(page_title="IDX Trader", layout="wide")
st.title("IDX Trader")
st.caption("Public data (yfinance, daily bars, delayed). Signals use the last closed day. "
           "Execute orders yourself in the Stockbit app. Not financial advice.")

with st.sidebar:
    mode = st.radio("Mode", ["swing", "daily"], format_func=lambda m: {
        "swing": "Swing (hold up to 10 days)", "daily": "Daily (next-day momentum)"}[m])
    capital = st.number_input("Capital (Rp)", min_value=1_000_000, value=10_000_000, step=1_000_000)
    max_alloc = st.slider("Max allocation per stock", 0.05, 1.0, 0.25, 0.05)
    min_value = st.number_input("Min avg daily value (Rp bn)", min_value=0.0, value=5.0, step=1.0) * 1e9
    codes = st.text_area("Universe (IDX codes)", " ".join(idx.UNIVERSE), height=160)
    only_signal = st.checkbox("Show only full signals", value=False)
    st.caption(f"Stop loss capped at {idx.MAX_LOSS:.0%} below entry. Fees: buy {idx.BUY_FEE:.2%}, sell {idx.SELL_FEE:.2%}.")


@st.cache_data(ttl=3600, show_spinner="Downloading prices...")
def load(code_list):
    return idx.fetch(list(code_list))


code_list = tuple(sorted({c.strip().upper() for c in codes.split() if c.strip()}))
if st.button("Refresh data"):
    load.clear()
data = load(code_list)
missing = set(code_list) - set(data)
if missing:
    st.warning("No data: " + " ".join(sorted(missing)))

df = idx.screen(data, mode, capital, max_alloc, min_value)
if df.empty:
    st.info("No stock passes the liquidity filter.")
    st.stop()
if only_signal:
    df = df[df["signal"]]

buys = df[df["signal"] & (df["lots"] > 0)]
st.subheader(f"Buy candidates ({len(buys)})")
if buys.empty:
    st.write("No full signal today. Waiting is a valid position.")
for _, r in buys.iterrows():
    st.markdown(
        f"**BUY {r['code']}** — {r['lots']} lot @ {r['entry']:,.0f} · SL {r['stop']:,.0f} ({r['loss%']}%) · "
        f"TP {r['target']:,.0f} · cost Rp {r['cost_rp']:,.0f} · max loss Rp {r['max_loss_rp']:,.0f} · "
        f"backtest {r['bt_trades']} trades, win {r['bt_win%']}%, avg {r['bt_avg%']}% · "
        f"[open in Stockbit](https://stockbit.com/symbol/{r['code']})"
    )

st.subheader("Screen")
st.dataframe(
    df, hide_index=True, use_container_width=True,
    column_config={"code": st.column_config.TextColumn(pinned=True)},
)
st.caption("Backtest: past 2 years, enter next open after each signal, exit at SL/TP/time, fees included. "
           "Few trades = weak evidence. Stockbit Auto Order: set SL and TP from the table after buying.")
