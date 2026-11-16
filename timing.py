"""When to act: IDX session clock, entry/exit schedule for a signal, hold/sell check for an open position."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import idx

WIB = ZoneInfo("Asia/Jakarta")
DATA_READY = time(16, 15)  # daily bar is final after post-trading


def sessions(day):
    """IDX regular-market phases for a weekday: (key, start, end). Friday has a longer break."""
    fri = day.weekday() == 4
    return [
        ("pre_open", time(8, 45), time(9, 0)),
        ("session1", time(9, 0), time(11, 30) if fri else time(12, 0)),
        ("break", time(11, 30) if fri else time(12, 0), time(14, 0) if fri else time(13, 30)),
        ("session2", time(14, 0) if fri else time(13, 30), time(15, 50)),
        ("pre_close", time(15, 50), time(16, 0)),
    ]


def is_trading_day(day):
    # shortcut: weekends only, IDX holidays (Lebaran, Natal, ...) not included; check the IDX calendar
    return day.weekday() < 5


def next_trading_day(day, n=1):
    while n:
        day += timedelta(days=1)
        n -= is_trading_day(day)
    return day


def market_status(now):
    """(phase key, datetime when it ends / market next opens). Phase 'closed' outside 08:45-16:00 on trading days."""
    d, t = now.date(), now.time()
    if is_trading_day(d):
        for key, start, end in sessions(d):
            if start <= t < end:
                return key, datetime.combine(d, end, WIB)
    nxt = d if is_trading_day(d) and t < time(8, 45) else next_trading_day(d)
    return "closed", datetime.combine(nxt, time(8, 45), WIB)


def drop_unfinished(df, now):
    """Remove today's bar while the market day is not over: a half-day bar is not a closed signal day."""
    if len(df) and df.index[-1].date() == now.date() and now.time() < DATA_READY:
        return df.iloc[:-1]
    return df


def hold_days(mode):
    """Max trading days to hold; ORB day trades are sold the same day."""
    return idx.MODES[mode]["hold"] if mode in idx.MODES else 1


def schedule(signal_day, mode):
    """Dates for a signal from the close of signal_day: buy day and last day to sell by time limit."""
    buy_day = next_trading_day(signal_day)
    return {"buy_day": buy_day, "exit_deadline": next_trading_day(buy_day, hold_days(mode) - 1)}


def exit_check(d, buy_day, entry, mode, stop=None, target=None):
    """Hold or sell for a position bought on buy_day at entry. d = idx.indicators() frame.
    stop/target: the ones saved with the position; otherwise the buy plan's (ATR of the day before buying)."""
    after_close = mode == "bsjp"  # bought in the pre-close auction: the buy day's own range came before the entry
    before = d[d.index.date < buy_day]
    since = d[d.index.date > buy_day] if after_close else d[d.index.date >= buy_day]
    if before.empty:
        raise ValueError("no price history before the buy date")
    if stop is None or target is None:
        plan_mode = mode if mode in idx.MODES else "daily"  # orb/bsjp added by hand: use the 1-day plan
        stop, target, _ = idx.plan(entry, float(before["atr"].iloc[-1]), plan_mode, 0, 0)
    deadline = next_trading_day(buy_day) if after_close else schedule(before.index[-1].date(), mode)["exit_deadline"]
    out = {"stop": stop, "target": target, "deadline": deadline, "days": len(since), "last": None, "pnl": 0.0}
    if since.empty:
        out["action"] = "wait_data"
        return out
    last = float(since["Close"].iloc[-1])
    out["last"], out["pnl"] = last, (last * (1 - idx.SELL_FEE) / (entry * (1 + idx.BUY_FEE)) - 1) * 100
    if (since["Low"] <= stop).any():
        out["action"] = "sell_stop"
    elif (since["High"] >= target).any():
        out["action"] = "sell_target"
    elif len(since) >= hold_days(mode):
        out["action"] = "sell_time"
    elif mode == "swing" and last < float(since["ema20"].iloc[-1]):
        out["action"] = "warn_trend"  # trend broke before stop/target: tighten or exit early
    else:
        out["action"] = "hold"
    return out


if __name__ == "__main__":
    at = lambda y, m, d, h, mi: datetime(y, m, d, h, mi, tzinfo=WIB)  # noqa: E731
    # 2026-11-16 is a Monday, 2026-11-20 a Friday
    assert market_status(at(2026, 11, 16, 8, 50))[0] == "pre_open"
    assert market_status(at(2026, 11, 16, 11, 45))[0] == "session1"
    assert market_status(at(2026, 11, 20, 11, 45))[0] == "break"  # Friday break starts 11:30
    assert market_status(at(2026, 11, 20, 13, 45))[0] == "break"
    assert market_status(at(2026, 11, 16, 15, 55))[0] == "pre_close"
    st, nxt = market_status(at(2026, 11, 15, 10, 0))  # Sunday
    assert st == "closed" and nxt == at(2026, 11, 16, 8, 45)
    assert market_status(at(2026, 11, 20, 17, 0))[1] == at(2026, 11, 23, 8, 45)  # Friday evening -> Monday
    assert market_status(at(2026, 11, 16, 7, 0))[1] == at(2026, 11, 16, 8, 45)
    s = schedule(date(2026, 11, 13), "swing")  # Friday signal
    assert s["buy_day"] == date(2026, 11, 16) and s["exit_deadline"] == date(2026, 11, 27)
    assert schedule(date(2026, 11, 13), "daily")["exit_deadline"] == date(2026, 11, 16)

    idxd = pd.bdate_range("2026-10-01", "2026-11-13")
    base = pd.DataFrame({"Open": 1000.0, "High": 1010.0, "Low": 990.0, "Close": 1000.0, "Volume": 1e6}, index=idxd)
    d = idx.indicators(base)
    r = exit_check(d, date(2026, 11, 10), 1000, "swing")
    assert r["action"] == "hold" and r["days"] == 4 and r["stop"] < 1000 < r["target"], r
    hit = base.copy()
    hit.loc["2026-11-12", "Low"] = 900.0
    assert exit_check(idx.indicators(hit), date(2026, 11, 10), 1000, "swing")["action"] == "sell_stop"
    assert exit_check(d, date(2026, 11, 3), 1000, "daily")["action"] == "sell_time"
    unfinished = drop_unfinished(base, at(2026, 11, 13, 10, 0))
    assert len(unfinished) == len(base) - 1 and len(drop_unfinished(base, at(2026, 11, 13, 17, 0))) == len(base)
    assert exit_check(d, date(2026, 11, 13), 1000, "orb", stop=985, target=1015)["action"] == "sell_time"
    assert exit_check(d, date(2026, 11, 13), 1000, "orb", stop=995, target=1005)["action"] == "sell_stop"
    assert schedule(date(2026, 11, 13), "orb")["exit_deadline"] == date(2026, 11, 16)
    # BSJP bought at Friday's close: Friday's own low must not trigger the stop; sell on Monday
    fri = exit_check(d, date(2026, 11, 13), 1000, "bsjp", stop=995, target=1015)
    assert fri["action"] == "wait_data" and fri["deadline"] == date(2026, 11, 16), fri
    assert exit_check(d, date(2026, 11, 12), 1000, "bsjp", stop=995, target=1015)["action"] == "sell_stop"
    assert exit_check(d, date(2026, 11, 12), 1000, "bsjp")["deadline"] == date(2026, 11, 13)  # no saved stop
    print("ok")
