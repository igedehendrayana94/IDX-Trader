"""Opening range breakout (ORB) day trading on IDX 5-minute bars, ported from day-trader-skill
(trader-entry / trader-exit / trader-timemachine) to IDX hours, ticks and fees.
Range 09:00-09:15 WIB. Entry: first 5-minute close above the range high before 14:30.
Stop: middle of the range (never more than 5% below entry). Target: 1.5R (1R barely clears IDX fees).
Exit: stop, target, or the closing price (sell in pre-closing 15:50-16:00)."""
from datetime import time

import pandas as pd
import yfinance as yf

import idx

RANGE_START, RANGE_END = time(9, 0), time(9, 15)
ENTRY_CUTOFF = time(14, 30)  # no new entries after this: too little time left in the day
PRE_CLOSE = time(15, 50)
RR = 1.5


def fetch_intraday(codes, period="60d"):
    """5-minute bars per code, Asia/Jakarta time. yfinance keeps about 60 days and is delayed ~10-15 minutes."""
    raw = yf.download([c + ".JK" for c in codes], period=period, interval="5m", group_by="ticker",
                      auto_adjust=False, progress=False, threads=True)
    out = {}
    for c in codes:
        try:
            df = raw[c + ".JK"].dropna(subset=["Close"])
        except KeyError:
            continue
        if len(df):
            out[c] = df
    return out


def plan(hi, lo, entry):
    stop = idx.round_tick(max((hi + lo) / 2, entry * (1 - idx.MAX_LOSS)), up=True)
    if stop >= entry:
        stop = entry - idx.tick(entry)
    return stop, idx.round_tick(entry + RR * (entry - stop), up=True)  # up: R:R stays >= RR for the risk gate


def day(bars, now=None):
    """ORB result for one trading day. now = current WIB datetime when the day is still running, else None."""
    t = bars.index.time
    rng = bars[(t >= RANGE_START) & (t < RANGE_END)]
    live = now is not None
    if live and now.time() < RANGE_END:
        return {"status": "forming"}
    if len(rng) < 2:
        return {"status": "no_range"}
    hi, lo = float(rng["High"].max()), float(rng["Low"].min())
    out = {"hi": hi, "lo": lo, "last": float(bars["Close"].iloc[-1])}
    after = bars[t >= RANGE_END]
    window = after[after.index.time < ENTRY_CUTOFF]
    trig = window[window["Close"] > hi]
    if trig.empty:
        out["status"] = "waiting" if live and now.time() < ENTRY_CUTOFF else "expired"
        return out
    entry = float(trig["Close"].iloc[0])
    stop, target = plan(hi, lo, entry)
    out.update(entry=entry, stop=stop, target=target, trigger_time=trig.index[0])
    rest = after[(after.index > trig.index[0]) & (after.index.time < PRE_CLOSE)]
    for _, b in rest.iterrows():
        if b["Low"] <= stop:  # stop first when both are touched (conservative)
            return {**out, "status": "stop", "exit": min(stop, float(b["Open"])), **_ret(entry, min(stop, float(b["Open"])), stop)}
        if b["High"] >= target:
            return {**out, "status": "target", "exit": max(target, float(b["Open"])), **_ret(entry, max(target, float(b["Open"])), stop)}
    if live and now.time() < time(16, 0):
        return {**out, "status": "open", **_ret(entry, out["last"], stop)}
    return {**out, "status": "time", "exit": out["last"], **_ret(entry, out["last"], stop)}


def _ret(entry, exit_px, stop):
    net = exit_px * (1 - idx.SELL_FEE) / (entry * (1 + idx.BUY_FEE)) - 1
    return {"ret": net, "r": (exit_px - entry) / (entry - stop)}


def days(bars):
    return [g for _, g in bars.groupby(bars.index.date)]


def timemachine(bars, today=None):
    """Replay every complete past day (today excluded). Returns stats of triggered trades."""
    res = [day(g) for g in days(bars) if g.index[0].date() != today]
    trades = [r for r in res if "ret" in r]
    s = pd.Series([r["ret"] for r in trades], dtype=float)
    return {"days": len(res), "trades": len(trades), "win%": (s > 0).mean() * 100 if len(s) else None,
            "avg%": s.mean() * 100 if len(s) else None,
            "avg_r": sum(r["r"] for r in trades) / len(trades) if trades else None}


if __name__ == "__main__":
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Jakarta")

    def mk(prices, d="2026-11-16"):
        """prices: list of (HH:MM, open, high, low, close)."""
        ix = pd.DatetimeIndex([pd.Timestamp(f"{d} {hm}", tz=tz) for hm, *_ in prices])
        return pd.DataFrame([p[1:] for p in prices], index=ix, columns=["Open", "High", "Low", "Close"])

    rng = [("09:00", 1000, 1010, 990, 1005), ("09:05", 1005, 1020, 1000, 1015), ("09:10", 1015, 1020, 1005, 1010)]
    # breakout at 09:20 close 1030 -> stop mid 1005, target 1030+1.5*25=1067.5 -> 1070 (rounded up: R:R never below 1.5)
    win = mk(rng + [("09:15", 1010, 1020, 1008, 1018), ("09:20", 1018, 1032, 1016, 1030),
                    ("10:00", 1030, 1070, 1028, 1060), ("15:45", 1060, 1062, 1055, 1058)])
    r = day(win)
    assert r["status"] == "target" and r["entry"] == 1030 and r["stop"] == 1005 and r["target"] == 1070, r
    assert r["ret"] > 0 and abs(r["r"] - 1.6) < 1e-9
    lose = mk(rng + [("09:20", 1018, 1032, 1016, 1030), ("10:00", 1030, 1031, 1000, 1002)])
    assert day(lose)["status"] == "stop" and day(lose)["ret"] < 0
    flat = mk(rng + [("09:20", 1010, 1018, 1005, 1012), ("15:45", 1012, 1015, 1008, 1010)])
    assert day(flat)["status"] == "expired"
    assert day(flat, datetime(2026, 11, 16, 10, 0, tzinfo=tz))["status"] == "waiting"
    assert day(win.iloc[:3], datetime(2026, 11, 16, 9, 10, tzinfo=tz))["status"] == "forming"
    late = mk(rng + [("14:35", 1010, 1040, 1010, 1035), ("15:45", 1035, 1036, 1030, 1032)])
    assert day(late)["status"] == "expired"  # breakout after the 14:30 cutoff is ignored
    timed = mk(rng + [("09:20", 1018, 1032, 1016, 1030), ("15:45", 1030, 1040, 1025, 1036), ("16:00", 1036, 1036, 1036, 1036)])
    assert day(timed)["status"] == "time" and day(timed)["exit"] == 1036
    assert day(timed.iloc[:4], datetime(2026, 11, 16, 11, 0, tzinfo=tz))["status"] == "open"
    lose_next_day = mk(rng + [("09:20", 1018, 1032, 1016, 1030), ("10:00", 1030, 1031, 1000, 1002)], "2026-11-17")
    tm = timemachine(pd.concat([win, lose_next_day]))
    assert tm["days"] == 2 and tm["trades"] == 2 and tm["win%"] == 50
    print("ok")
