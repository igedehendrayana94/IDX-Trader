import streamlit as st

import idx
import ml

# Indonesian follows KBBI forms and the Jutif term rules: standard Indonesian where it exists,
# English in italics where no standard term exists (swing, stop loss, backtest, walk-forward, machine learning).
T = {
    "en": {
        "caption": "Public data (yfinance, daily bars, delayed). Signals use the last closed trading day. "
                   "Place orders yourself in the Stockbit app. Not investment advice.",
        "mode": "Mode", "swing": "Swing (hold up to 10 days)", "daily": "Daily (next-day momentum)",
        "capital": "Capital (Rp)", "alloc": "Max allocation per stock",
        "min_value": "Min avg daily trading value (Rp billion)", "universe": "Stock list (IDX codes)",
        "only_signal": "Show only full signals",
        "rules": "Stop loss capped at {loss} below entry. Fees: buy {buy}, sell {sell}.",
        "downloading": "Downloading prices...", "training": "Training ML model (walk-forward)...",
        "refresh": "Refresh data", "no_data": "No data: ", "no_liquid": "No stock passes the liquidity filter.",
        "buys": "Buy candidates ({n})", "no_signal": "No full signal today. Not buying is a valid decision.",
        "buy_line": "**BUY {code}** — {lots} lot @ {entry} · SL {stop} ({loss}%) · TP {target} · ML {prob} · "
                    "cost Rp {cost} · max loss Rp {maxloss} · backtest {n} trades, win {win}%, avg {avg}% · "
                    "[open in Stockbit](https://stockbit.com/symbol/{code})",
        "ml_title": "Machine learning prediction",
        "ml_caption": "Gradient boosting model (scikit-learn HistGradientBoosting) trained on price, trend, "
                      "momentum, volume and market features. ml_prob is the probability that this mode's trade "
                      "plan (entry, SL, TP, holding time) ends in net profit. Validated walk-forward: each block "
                      "is predicted by a model trained only on earlier data.",
        "auc": "Avg AUC (test data)",
        "auc_help": "AUC measured on out-of-sample test data. 0.5 = coin flip. Above ~0.55 = useful.",
        "edge": "The model shows an edge in testing.",
        "no_edge": "No edge in testing. Ignore ml_prob for this mode.",
        "top": "Top ML picks: ", "screen": "Screening results",
        "footer": "Backtest: past 5 years, entry at the next open after each signal, exit at SL, TP or time "
                  "limit, fees included. Few trades means weak evidence. Stockbit Auto Order: set SL and TP "
                  "from the table after buying.",
        "cols": {}, "wf_cols": {"auc": "AUC"},
    },
    "id": {
        "caption": "Data publik (yfinance, data harian dengan jeda). Sinyal memakai hari perdagangan terakhir yang "
                   "sudah ditutup. Pemesanan saham dilakukan sendiri melalui aplikasi Stockbit. Bukan saran investasi.",
        "mode": "Mode", "swing": "*Swing* (tahan hingga 10 hari)", "daily": "Harian (momentum hari berikutnya)",
        "capital": "Modal (Rp)", "alloc": "Alokasi maksimum per saham",
        "min_value": "Nilai transaksi rata-rata harian minimum (miliar Rp)", "universe": "Daftar saham (kode BEI)",
        "only_signal": "Tampilkan hanya sinyal penuh",
        "rules": "*Stop loss* dibatasi paling jauh {loss} di bawah harga masuk. Biaya: beli {buy}, jual {sell}.",
        "downloading": "Mengunduh data harga...", "training": "Melatih model machine learning (walk-forward)...",
        "refresh": "Perbarui data", "no_data": "Data tidak tersedia: ",
        "no_liquid": "Tidak ada saham yang lolos filter likuiditas.",
        "buys": "Kandidat beli ({n})",
        "no_signal": "Belum ada sinyal penuh hari ini. Tidak membeli juga merupakan keputusan yang sah.",
        "buy_line": "**BELI {code}** — {lots} lot @ {entry} · SL {stop} ({loss}%) · TP {target} · ML {prob} · "
                    "biaya Rp {cost} · rugi maks. Rp {maxloss} · uji historis {n} transaksi, menang {win}%, "
                    "rata-rata {avg}% · [buka di Stockbit](https://stockbit.com/symbol/{code})",
        "ml_title": "Prediksi *machine learning*",
        "ml_caption": "Model *gradient boosting* (scikit-learn HistGradientBoosting) dilatih dengan fitur harga, "
                      "tren, momentum, volume, dan kondisi pasar. ml_prob adalah probabilitas rencana transaksi "
                      "pada mode ini (harga masuk, SL, TP, lama tahan) berakhir dengan laba bersih. Validasi "
                      "memakai metode *walk-forward*: setiap blok diprediksi oleh model yang hanya dilatih dengan "
                      "data sebelumnya.",
        "auc": "AUC rata-rata (data uji)",
        "auc_help": "AUC dihitung pada data uji di luar sampel. 0,5 = sama dengan menebak acak. Di atas ±0,55 = berguna.",
        "edge": "Model menunjukkan keunggulan pada pengujian.",
        "no_edge": "Model tidak menunjukkan keunggulan pada pengujian. Abaikan ml_prob untuk mode ini.",
        "top": "Pilihan teratas model: ", "screen": "Hasil penyaringan",
        "footer": "Uji historis (*backtest*): 5 tahun terakhir, masuk pada harga pembukaan setelah setiap sinyal, "
                  "keluar pada SL, TP, atau batas waktu, sudah termasuk biaya. Jumlah transaksi yang sedikit "
                  "berarti bukti lemah. Fitur Auto Order di Stockbit: pasang SL dan TP dari tabel setelah membeli.",
        "cols": {"code": "kode", "date": "tanggal", "score": "skor", "signal": "sinyal", "close": "penutupan",
                 "chg%": "ubah%", "entry": "masuk", "stop": "SL", "target": "TP", "loss%": "rugi%",
                 "lots": "lot", "cost_rp": "biaya_rp", "max_loss_rp": "rugi_maks_rp",
                 "value20_bn": "nilai20_miliar", "bt_trades": "uji_transaksi", "bt_win%": "uji_menang%",
                 "bt_avg%": "uji_rata%", "uptrend": "tren_naik", "macd_up": "macd_naik",
                 "strong_close": "tutup_kuat", "vol_spike": "lonjakan_volume", "green": "naik"},
        "wf_cols": {"auc": "AUC", "test_from": "uji_dari", "test_to": "uji_sampai", "base_win%": "menang_dasar%",
                    "top10_win%": "menang_top10%", "base_avg%": "rata_dasar%", "top10_avg%": "rata_top10%",
                    "n_test": "n_uji"},
    },
}

st.set_page_config(page_title="IDX Trader", layout="wide")

with st.sidebar:
    lang = st.radio("Language / Bahasa", ["id", "en"], horizontal=True,
                    format_func=lambda k: {"id": "Indonesia", "en": "English"}[k])
t = T[lang]


def num(x, dec=0):
    """Indonesian uses '.' for thousands and ',' for decimals."""
    s = f"{x:,.{dec}f}"
    return s.translate(str.maketrans(",.", ".,")) if lang == "id" else s


st.title("IDX Trader")
st.caption(t["caption"])

with st.sidebar:
    mode = st.radio(t["mode"], ["swing", "daily"], format_func=lambda m: t[m])
    capital = st.number_input(t["capital"], min_value=1_000_000, value=10_000_000, step=1_000_000)
    max_alloc = st.slider(t["alloc"], 0.05, 1.0, 0.25, 0.05)
    min_value = st.number_input(t["min_value"], min_value=0.0, value=5.0, step=1.0) * 1e9
    codes = st.text_area(t["universe"], " ".join(idx.UNIVERSE), height=160)
    only_signal = st.checkbox(t["only_signal"], value=False)
    st.caption(t["rules"].format(loss=f"{num(idx.MAX_LOSS * 100)}%", buy=f"{num(idx.BUY_FEE * 100, 2)}%",
                                 sell=f"{num(idx.SELL_FEE * 100, 2)}%"))


@st.cache_data(ttl=3600, show_spinner=False)
def load(code_list):
    return idx.fetch(list(code_list), period="5y")


@st.cache_data(ttl=3600, show_spinner=False)
def train(code_list, mode):
    p = ml.dataset(load(code_list), mode)
    return ml.walk_forward(p, mode), ml.predict_latest(p)


code_list = tuple(sorted({c.strip().upper() for c in codes.split() if c.strip()}))
if st.button(t["refresh"]):
    load.clear()
    train.clear()
with st.spinner(t["downloading"]):
    data = load(code_list)
missing = set(code_list) - set(data)
if missing:
    st.warning(t["no_data"] + " ".join(sorted(missing)))

df = idx.screen(data, mode, capital, max_alloc, min_value)
if df.empty:
    st.info(t["no_liquid"])
    st.stop()
with st.spinner(t["training"]):
    wf, prob = train(code_list, mode)
df.insert(4, "ml_prob", df["code"].map(prob).round(3))
auc = wf["auc"].mean() if len(wf) else 0.5
has_edge = auc >= 0.53  # shortcut: fixed AUC bar, replace with a significance test if folds grow
if only_signal:
    df = df[df["signal"]]

buys = df[df["signal"] & (df["lots"] > 0)]
st.subheader(t["buys"].format(n=len(buys)))
if buys.empty:
    st.write(t["no_signal"])
for _, r in buys.iterrows():
    st.markdown(t["buy_line"].format(
        code=r["code"], lots=num(r["lots"]), entry=num(r["entry"]), stop=num(r["stop"]), loss=num(r["loss%"], 2),
        target=num(r["target"]), prob=f"{num(r['ml_prob'] * 100)}%", cost=num(r["cost_rp"]),
        maxloss=num(r["max_loss_rp"]), n=r["bt_trades"], win=r["bt_win%"], avg=r["bt_avg%"],
    ))

st.subheader(t["ml_title"])
st.caption(t["ml_caption"])
c1, c2 = st.columns([1, 3])
c1.metric(t["auc"], num(auc, 3), help=t["auc_help"])
(c1.success if has_edge else c1.error)(t["edge"] if has_edge else t["no_edge"])
c2.dataframe(wf.rename(columns=t["wf_cols"]), hide_index=True, use_container_width=True)
top = prob.sort_values(ascending=False).head(10)
st.write(t["top"] + " · ".join(f"**{c}** {num(v * 100)}%" for c, v in top.items()))

st.subheader(t["screen"])
code_col = t["cols"].get("code", "code")
st.dataframe(
    df.rename(columns=t["cols"]), hide_index=True, use_container_width=True,
    column_config={code_col: st.column_config.TextColumn(pinned=True)},
)
st.caption(t["footer"])
