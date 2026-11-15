"""Trade journal: local JSON storage for positions and closed trades, performance stats, weekly digest, coaching notes.
Ideas from claude-trading-skills (trade-performance-coach, weekly-performance-digest, signal-postmortem)."""
import json
from datetime import date

import pandas as pd

import idx


def load(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, default=str))


def close(pos, exit_price, exit_day, reason, stop):
    """Journal row for a position sold at exit_price. stop = the plan's stop (for the R multiple)."""
    entry, shares = pos["price"], pos["lots"] * idx.LOT
    per_share = exit_price * (1 - idx.SELL_FEE) - entry * (1 + idx.BUY_FEE)
    return {
        "code": pos["code"], "mode": pos["mode"], "buy_date": pos["date"], "entry": entry, "lots": pos["lots"],
        "exit_date": exit_day.isoformat(), "exit": exit_price, "reason": reason, "stop": stop,
        "pnl_rp": round(per_share * shares), "pnl_pct": round(per_share / (entry * (1 + idx.BUY_FEE)) * 100, 2),
        "r": round((exit_price - entry) / (entry - stop), 2) if entry > stop else None,
    }


def stats(rows):
    if not rows:
        return None
    t = pd.DataFrame(rows)
    wins, losses = t[t["pnl_rp"] > 0], t[t["pnl_rp"] <= 0]
    streak = best = 0
    for p in t.sort_values("exit_date")["pnl_rp"]:
        streak = streak + 1 if p <= 0 else 0
        best = max(best, streak)
    gross_loss = -losses["pnl_rp"].sum()
    return {
        "n": len(t), "win%": len(wins) / len(t) * 100, "total": t["pnl_rp"].sum(),
        "expectancy": t["pnl_rp"].mean(),  # average Rp per trade
        "avg_win%": wins["pnl_pct"].mean() if len(wins) else 0.0,
        "avg_loss%": losses["pnl_pct"].mean() if len(losses) else 0.0,
        "profit_factor": wins["pnl_rp"].sum() / gross_loss if gross_loss > 0 else None,
        "avg_r": t["r"].dropna().mean() if t["r"].notna().any() else None,
        "max_loss_streak": best,
    }


def weekly(rows):
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t["week"] = pd.to_datetime(t["exit_date"]).dt.strftime("%G-W%V")
    return (t.groupby("week").agg(trades=("pnl_rp", "size"), win=("pnl_rp", lambda x: (x > 0).mean() * 100),
                                  pnl_rp=("pnl_rp", "sum"))
            .sort_index(ascending=False).reset_index())


def coach(rows, s):
    """Keys of coaching notes, most important first."""
    notes = []
    if any(r["pnl_pct"] < -(idx.MAX_LOSS * 100 + 1) for r in rows):
        notes.append("stop_ignored")  # a loss bigger than the planned stop: stop loss was not respected
    if s["avg_loss%"] and s["avg_win%"] and abs(s["avg_loss%"]) > s["avg_win%"]:
        notes.append("loss_bigger")
    if s["max_loss_streak"] >= 3:
        notes.append("streak")
    if s["n"] < 20:
        notes.append("few_trades")
    elif s["expectancy"] > 0:
        notes.append("positive")
    return notes


if __name__ == "__main__":
    pos = {"code": "BBCA", "mode": "swing", "date": "2026-11-10", "price": 5000, "lots": 2}
    w = close(pos, 5500, date(2026, 11, 13), "target", 4750)
    assert w["pnl_rp"] == round((5500 * 0.9975 - 5000 * 1.0015) * 200) and w["r"] == 2.0
    l1 = close(pos, 4750, date(2026, 11, 16), "stop", 4750)
    l2 = close(pos, 4500, date(2026, 11, 17), "manual", 4750)  # sold below the stop
    s = stats([w, l1, l2])
    assert s["n"] == 3 and round(s["win%"]) == 33 and s["max_loss_streak"] == 2 and s["profit_factor"] is not None
    notes = coach([w, l1, l2], s)
    assert notes[0] == "stop_ignored" and "few_trades" in notes
    wk = weekly([w, l1, l2])
    assert wk["week"].tolist() == ["2026-W47", "2026-W46"] and wk["trades"].tolist() == [2, 1]
    assert stats([]) is None and weekly([]).empty
    print("ok")
