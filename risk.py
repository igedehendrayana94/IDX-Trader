"""Market regime traffic light, risk-based position sizing, pre-trade risk gate (PASS/BLOCK).
Ideas ported from claude-trading-skills (market-breadth, distribution days, position-sizer,
drawdown-circuit-breaker, pre-trade-discipline-gate) and day-trader-skill (trader-budget, trader-risk), using IDX data."""
from datetime import date

import pandas as pd

import idx
import timing

DEFAULT_LIMITS = {
    "risk_pct": 1.0,        # max loss per trade, % of capital
    "daily_loss_pct": 3.0,  # stop trading for the day after this realised loss
    "max_open": 5,          # open positions at once
    "max_trades_day": 3,    # new buys per day
    "min_rr": 1.5,          # reward:risk
    "loss_streak": 3,       # consecutive losing trades -> pause one trading day
}


# ---------- regime ----------
def regime_series(data, ihsg):
    """Daily traffic light from IHSG trend, IHSG distribution days and breadth of the stock list.
    green: IHSG above a rising 50-day EMA and most stocks in uptrends -> trade normally
    yellow: mixed -> half size
    red: IHSG below its 50-day EMA and weak breadth, or heavy distribution -> no new buys"""
    c, v = ihsg["Close"], ihsg["Volume"]
    ema50 = c.ewm(span=50, adjust=False).mean()
    # IBD distribution day: index down >= 0.2% on higher volume than the day before; count in last 25 sessions
    dist = ((c.pct_change() <= -0.002) & (v > v.shift())).rolling(25).sum()
    above = pd.DataFrame({k: d["Close"] > d["Close"].ewm(span=50, adjust=False).mean() for k, d in data.items()})
    r = pd.DataFrame({
        "ihsg_up": c > ema50, "ema_rising": ema50 > ema50.shift(10), "dist_days": dist,
        "breadth": above.reindex(c.index).mean(axis=1) * 100,
    })
    score = r["ihsg_up"].astype(int) + r["ema_rising"].astype(int) + (r["breadth"] >= 50) + (r["dist_days"] < 5)
    r["light"] = "yellow"
    r.loc[(score >= 3) & r["ihsg_up"], "light"] = "green"
    r.loc[(score <= 1) | (r["dist_days"] >= 7), "light"] = "red"
    return r


SIZE_FACTOR = {"green": 1.0, "yellow": 0.5, "red": 0.0}


# ---------- sizing ----------
size_lots = idx.size_lots  # lives in idx so the screener can use it without a circular import


# ---------- gate ----------
def _closed_today(journal, day):
    return [j for j in journal if j["exit_date"] == day.isoformat()]


def gate(entry, stop, target, lots, capital, light, positions, journal, today, limits=DEFAULT_LIMITS,
         window_open=True, news_red=0):
    """Pre-trade checklist. Returns list of (check key, passed, detail dict). Any failure = BLOCK."""
    cost = lots * idx.LOT * entry * (1 + idx.BUY_FEE)
    open_cost = sum(p["lots"] * idx.LOT * p["price"] * (1 + idx.BUY_FEE) for p in positions)
    realised = sum(j["pnl_rp"] for j in _closed_today(journal, today))
    buys_today = sum(p["date"] == today.isoformat() for p in positions) + \
        sum(j["buy_date"] == today.isoformat() for j in journal)
    rr = (target - entry) / (entry - stop) if entry > stop else 0
    # circuit breaker: last N closed trades all losses -> no buys for the rest of that day and the next trading day
    closed = sorted(journal, key=lambda j: j["exit_date"])[-limits["loss_streak"]:]
    streak = len(closed) == limits["loss_streak"] and all(j["pnl_rp"] < 0 for j in closed)
    paused_until = timing.next_trading_day(date.fromisoformat(closed[-1]["exit_date"]), 2) if streak else None
    return [
        ("regime", light != "red", {"light": light}),
        ("lots", lots >= 1, {"lots": lots}),
        ("rr", rr >= limits["min_rr"], {"rr": rr, "min": limits["min_rr"]}),
        ("cash", open_cost + cost <= capital, {"need": cost, "free": capital - open_cost}),
        ("max_open", len(positions) < limits["max_open"], {"n": len(positions), "max": limits["max_open"]}),
        ("trades_day", buys_today < limits["max_trades_day"], {"n": buys_today, "max": limits["max_trades_day"]}),
        ("daily_loss", realised > -capital * limits["daily_loss_pct"] / 100,
         {"loss": -realised, "max": capital * limits["daily_loss_pct"] / 100}),
        ("streak", not (paused_until and today < paused_until), {"until": paused_until, "n": limits["loss_streak"]}),
        ("window", window_open, {}),
        ("news", not news_red, {"n": news_red}),  # suspension/PKPU/default/UMA headline in the last 7 days
    ]


def passed(checks):
    return all(ok for _, ok, _ in checks)


if __name__ == "__main__":
    # sizing: Rp 10 jt, 1% risk = Rp 100.000; entry 5.000 stop 4.750 -> ~258 loss/share incl. fees -> 3 lots
    assert size_lots(10_000_000, 1, 5000, 4750, 1.0) == 3
    assert size_lots(10_000_000, 1, 5000, 4750, 1.0, factor=0.5) == 1
    assert size_lots(10_000_000, 1, 5000, 4750, 0.05) == 0  # allocation cap (Rp 500.000 < 1 lot)
    assert size_lots(10_000_000, 1, 5000, 5000, 1.0) == 0 and size_lots(10_000_000, 1, 5000, 4750, 1, 0) == 0
    today = date(2026, 11, 16)
    args = dict(entry=5000, stop=4750, target=5500, lots=3, capital=10_000_000, today=today)
    assert passed(gate(light="green", positions=[], journal=[], **args))
    assert not passed(gate(light="red", positions=[], journal=[], **args))
    assert not passed(gate(light="green", positions=[], journal=[], news_red=1, **args))  # red-flag headline blocks
    loss = lambda d, rp=-50_000: {"exit_date": d, "buy_date": d, "pnl_rp": rp}  # noqa: E731
    j3 = [loss("2026-11-12"), loss("2026-11-13"), loss("2026-11-13")]
    chk = dict((k, ok) for k, ok, _ in gate(light="green", positions=[], journal=j3, **args))
    assert not chk["streak"]  # 3 losses up to Fri 13-11 -> Mon 16-11 blocked
    chk = dict((k, ok) for k, ok, _ in gate(light="green", positions=[], journal=j3, **{**args, "today": date(2026, 11, 17)}))
    assert chk["streak"]  # Tue 17-11 trading resumes
    big = [loss("2026-11-16", -400_000)]
    assert not dict((k, ok) for k, ok, _ in gate(light="green", positions=[], journal=big, **args))["daily_loss"]
    pos = [{"code": "X", "lots": 30, "price": 3000, "date": "2026-11-10"}]
    assert not dict((k, ok) for k, ok, _ in gate(light="green", positions=pos, journal=[], **args))["cash"]
    assert not dict((k, ok) for k, ok, _ in gate(light="green", positions=[], journal=[], **{**args, "target": 5100}))["rr"]

    idxd = pd.bdate_range("2025-01-01", periods=300)
    up = pd.DataFrame({"Close": [1000 + i for i in range(300)], "Volume": 1e6}, index=idxd)
    down = pd.DataFrame({"Close": [2000 - 3 * i for i in range(300)], "Volume": [1e6 + i for i in range(300)]}, index=idxd)
    assert regime_series({"A": up, "B": up}, up)["light"].iloc[-1] == "green"
    assert regime_series({"A": down, "B": down}, down)["light"].iloc[-1] == "red"
    print("ok")
