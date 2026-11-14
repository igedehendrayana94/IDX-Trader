"""IDX screener core: data, indicators, signals, trade plan, backtest. Public data only (yfinance)."""
import math

import pandas as pd
import yfinance as yf

# shortcut: hardcoded LQ45-like universe, edit in the app sidebar or update from idx.co.id each review period.
UNIVERSE = (
    "AADI ACES ADRO AKRA AMMN AMRT ANTM ARTO ASII BBCA BBNI BBRI BBTN BMRI BRIS BRPT CPIN CTRA "
    "ESSA EXCL GOTO HRUM ICBP INCO INDF INKP ISAT ITMG JPFA JSMR KLBF MAPA MAPI MBMA MDKA MEDC "
    "PGAS PGEO PTBA SIDO SMGR SMRA TLKM TOWR UNTR UNVR"
).split()

# shortcut: names hardcoded for the default list; unknown codes show no name
NAMES = {
    "AADI": "Adaro Andalan Indonesia Tbk.", "ACES": "Aspirasi Hidup Indonesia Tbk.",
    "ADRO": "Alamtri Resources Indonesia Tbk.", "AKRA": "AKR Corporindo Tbk.",
    "AMMN": "Amman Mineral Internasional Tbk.", "AMRT": "Sumber Alfaria Trijaya Tbk.",
    "ANTM": "Aneka Tambang Tbk.", "ARTO": "Bank Jago Tbk.", "ASII": "Astra International Tbk.",
    "BBCA": "Bank Central Asia Tbk.", "BBNI": "Bank Negara Indonesia (Persero) Tbk.",
    "BBRI": "Bank Rakyat Indonesia (Persero) Tbk.", "BBTN": "Bank Tabungan Negara (Persero) Tbk.",
    "BMRI": "Bank Mandiri (Persero) Tbk.", "BRIS": "Bank Syariah Indonesia Tbk.", "BRPT": "Barito Pacific Tbk.",
    "CPIN": "Charoen Pokphand Indonesia Tbk.", "CTRA": "Ciputra Development Tbk.",
    "ESSA": "ESSA Industries Indonesia Tbk.", "EXCL": "XLSMART Telecom Sejahtera Tbk.",
    "GOTO": "GoTo Gojek Tokopedia Tbk.", "HRUM": "Harum Energy Tbk.", "ICBP": "Indofood CBP Sukses Makmur Tbk.",
    "INCO": "Vale Indonesia Tbk.", "INDF": "Indofood Sukses Makmur Tbk.", "INKP": "Indah Kiat Pulp & Paper Tbk.",
    "ISAT": "Indosat Tbk.", "ITMG": "Indo Tambangraya Megah Tbk.", "JPFA": "Japfa Comfeed Indonesia Tbk.",
    "JSMR": "Jasa Marga (Persero) Tbk.", "KLBF": "Kalbe Farma Tbk.", "MAPA": "Map Aktif Adiperkasa Tbk.",
    "MAPI": "Mitra Adiperkasa Tbk.", "MBMA": "Merdeka Battery Materials Tbk.", "MDKA": "Merdeka Copper Gold Tbk.",
    "MEDC": "Medco Energi Internasional Tbk.", "PGAS": "Perusahaan Gas Negara Tbk.",
    "PGEO": "Pertamina Geothermal Energy Tbk.", "PTBA": "Bukit Asam Tbk.",
    "SIDO": "Industri Jamu dan Farmasi Sido Muncul Tbk.", "SMGR": "Semen Indonesia (Persero) Tbk.",
    "SMRA": "Summarecon Agung Tbk.", "TLKM": "Telkom Indonesia (Persero) Tbk.",
    "TOWR": "Sarana Menara Nusantara Tbk.", "UNTR": "United Tractors Tbk.", "UNVR": "Unilever Indonesia Tbk.",
}

BUY_FEE, SELL_FEE = 0.0015, 0.0025  # typical IDX broker fee; sell includes 0.1% final tax
MAX_LOSS = 0.05  # user rule: stop loss never more than 5% below entry
LOT = 100

MODES = {
    # atr_mult = stop distance in ATR, hold = max days before time exit, rr = reward:risk for target
    "swing": {"atr_mult": 1.5, "hold": 10, "rr": 2.0},
    "daily": {"atr_mult": 1.0, "hold": 1, "rr": 1.5},
}


def tick(price):
    """IDX price fraction (tick size) for a given price."""
    if price < 200:
        return 1
    if price < 500:
        return 2
    if price < 2000:
        return 5
    if price < 5000:
        return 10
    return 25


def round_tick(price, up=False):
    t = tick(price)
    return (math.ceil if up else math.floor)(price / t) * t


def fetch(codes, period="2y"):
    """Daily unadjusted OHLCV per code (matches the prices Stockbit shows)."""
    raw = yf.download([c + ".JK" for c in codes], period=period, interval="1d",
                      group_by="ticker", auto_adjust=False, progress=False, threads=True)
    out = {}
    for c in codes:
        try:
            df = raw[c + ".JK"].dropna(subset=["Close"])
        except KeyError:
            continue
        df = df[df["Volume"] > 0]
        if len(df) >= 60:
            out[c] = df
    return out


def fetch_ihsg(period="2y"):
    """IHSG (Jakarta Composite, ^JKSE) daily bars."""
    df = yf.download("^JKSE", period=period, interval="1d", auto_adjust=False, progress=False)
    df.columns = df.columns.get_level_values(0)  # yfinance returns (Price, Ticker) columns
    return df.dropna(subset=["Close"])


def load_foreign(folder="data/foreign"):
    """Foreign flow from IDX 'Ringkasan Saham' files downloaded by hand from idx.co.id
    (Data Pasar > Ringkasan Perdagangan > Ringkasan Saham). One file per trading day, date in the
    file name as YYYYMMDD. Returns long frame: date, code, fnet (foreign buy - sell, shares)."""
    import re
    from pathlib import Path
    rows = []
    for f in sorted(Path(folder).glob("*")):
        m = re.search(r"(20\d{6})", f.name)
        if not m or f.suffix.lower() not in (".xlsx", ".xls", ".csv"):
            continue
        t = pd.read_csv(f) if f.suffix.lower() == ".csv" else pd.read_excel(f)
        cols = {c.lower().strip(): c for c in t.columns}
        try:
            code, fb, fs = cols["kode saham"], cols["foreign buy"], cols["foreign sell"]
        except KeyError:
            raise ValueError(f"{f.name}: expected columns 'Kode Saham', 'Foreign Buy', 'Foreign Sell'")
        rows.append(pd.DataFrame({"date": pd.Timestamp(m.group(1)), "code": t[code].astype(str).str.strip(),
                                  "fnet": pd.to_numeric(t[fb], errors="coerce") - pd.to_numeric(t[fs], errors="coerce")}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "code", "fnet"])


def indicators(df):
    d = df.copy()
    c, h, l = d["Close"], d["High"], d["Low"]
    d["ema20"] = c.ewm(span=20, adjust=False).mean()
    d["ema50"] = c.ewm(span=50, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, 1e-9))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d["vol20"] = d["Volume"].rolling(20).mean().shift()  # prior 20 days, excludes today
    d["value20"] = (c * d["Volume"]).rolling(20).mean()
    d["high20"] = h.rolling(20).max().shift()
    rng = (h - l).replace(0, float("nan"))
    d["close_pos"] = ((c - l) / rng).fillna(0.5)  # 1 = closed at day high
    d["chg"] = c.pct_change()
    return d


def conditions(d, mode):
    """Boolean condition columns for a mode; all True = signal."""
    if mode == "swing":
        return pd.DataFrame({
            "uptrend": (d["Close"] > d["ema20"]) & (d["ema20"] > d["ema50"]),
            "rsi_ok": d["rsi"].between(45, 70),
            "macd_up": (d["macd_hist"] > 0) & (d["macd_hist"] > d["macd_hist"].shift()),
            "volume": d["Volume"] > 1.2 * d["vol20"],
        })
    return pd.DataFrame({
        "breakout": d["Close"] > d["high20"],
        "strong_close": d["close_pos"] >= 0.75,
        "vol_spike": d["Volume"] >= 2 * d["vol20"],
        "green": d["chg"] > 0,
    })


def plan(entry, atr, mode, capital, max_alloc):
    """Stop, target, lots for one trade. Stop capped at MAX_LOSS below entry."""
    m = MODES[mode]
    stop = max(entry - m["atr_mult"] * atr, entry * (1 - MAX_LOSS))
    stop = round_tick(stop, up=True)  # rounding up keeps loss within the cap
    if stop >= entry:
        stop = entry - tick(entry)
    target = round_tick(entry + m["rr"] * (entry - stop))
    lots = int(capital * max_alloc // (entry * LOT * (1 + BUY_FEE)))
    return stop, target, lots


def outcome(arr, i, mode):
    """Trade from a signal on day i: enter next open, exit at stop/target/time. Returns (net return, exit index)."""
    o, h, l, c, atr = arr
    hold, n = MODES[mode]["hold"], len(c)
    e = i + 1
    entry = o[e]
    stop, target, _ = plan(entry, atr[i], mode, 0, 0)
    j = min(e + hold - 1, n - 1)
    exit_px = c[j]
    for k in range(e, j + 1):
        if l[k] <= stop:  # assume stop hit first when both touched (conservative)
            exit_px, j = min(stop, o[k]), k
            break
        if h[k] >= target:
            exit_px, j = max(target, o[k]), k
            break
    return exit_px * (1 - SELL_FEE) / (entry * (1 + BUY_FEE)) - 1, j


def ohlca(d):
    return tuple(d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "atr"))


def backtest(d, mode):
    """Rule signals, one position at a time, fees included."""
    sig = conditions(d, mode).all(axis=1).to_numpy()
    arr = ohlca(d)
    rets, i, n = [], 50, len(d)
    while i < n - 1:
        if not sig[i]:
            i += 1
            continue
        r, j = outcome(arr, i, mode)
        rets.append(r)
        i = j + 1
    if not rets:
        return {"trades": 0, "win_rate": None, "avg_ret": None}
    s = pd.Series(rets)
    return {"trades": len(s), "win_rate": (s > 0).mean(), "avg_ret": s.mean()}


def screen(data, mode, capital, max_alloc, min_value):
    rows = []
    for code, df in data.items():
        d = indicators(df)
        last = d.iloc[-1]
        if last["value20"] < min_value:
            continue
        cond = conditions(d, mode).iloc[-1]
        entry = float(last["Close"])
        stop, target, lots = plan(entry, float(last["atr"]), mode, capital, max_alloc)
        bt = backtest(d, mode)
        rows.append({
            "code": code, "date": d.index[-1].date(), "score": int(cond.sum()), "signal": bool(cond.all()),
            "close": entry, "chg%": round(last["chg"] * 100, 2), "rsi": round(last["rsi"], 1),
            "entry": entry, "stop": stop, "target": target,
            "loss%": round((stop / entry - 1) * 100, 2), "lots": lots,
            "cost_rp": round(lots * LOT * entry * (1 + BUY_FEE)),
            "max_loss_rp": round(lots * LOT * (entry * (1 + BUY_FEE) - stop * (1 - SELL_FEE))),
            "value20_bn": round(last["value20"] / 1e9, 1),
            "bt_trades": bt["trades"], "bt_win%": None if bt["win_rate"] is None else round(bt["win_rate"] * 100),
            "bt_avg%": None if bt["avg_ret"] is None else round(bt["avg_ret"] * 100, 2),
            **{k: bool(v) for k, v in cond.items()},
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["signal", "score", "value20_bn"], ascending=False) if len(df) else df


if __name__ == "__main__":
    # offline self-check of the money/tick logic
    assert tick(150) == 1 and tick(450) == 2 and tick(1990) == 5 and tick(4990) == 10 and tick(9000) == 25
    assert round_tick(4853) == 4850 and round_tick(4853, up=True) == 4860
    for mode in MODES:
        for entry, atr in [(4850, 500), (180, 2), (9000, 50), (1000, 300)]:
            stop, target, lots = plan(entry, atr, mode, 10_000_000, 0.25)
            assert stop < entry and (entry - stop) / entry <= MAX_LOSS + 1e-9, (mode, entry, stop)
            assert stop % tick(stop) == 0 and target > entry
            assert lots * LOT * entry * (1 + BUY_FEE) <= 2_500_000
    # foreign flow file parsing
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pd.DataFrame({"No": [1, 2], "Kode Saham": ["BBCA", "TLKM"], "Foreign Sell": [100, 50],
                      "Foreign Buy": [300, 20]}).to_excel(f"{tmp}/Ringkasan Saham-20261113.xlsx", index=False)
        fr = load_foreign(tmp)
        assert fr["fnet"].tolist() == [200, -30] and fr["date"].iloc[0] == pd.Timestamp("2026-11-13"), fr
        assert load_foreign(tmp + "/missing").empty
    print("ok")
