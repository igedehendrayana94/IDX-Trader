# IDX-Trader

Small dashboard that screens Indonesian (IDX) stocks and gives buy candidates with stop loss, target and lot size. Orders are placed manually in the Stockbit app (Stockbit has no official API; unofficial token access was rejected by the user).

## Stack
- Python 3.13 venv in `.venv/` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`)
- Data: yfinance daily bars, `CODE.JK`, unadjusted (matches Stockbit prices). Public data only.
- UI: Streamlit (`.venv/bin/streamlit run app.py`, port 8501)

## Files
- `idx.py`: fetch, indicators (EMA20/50, RSI14, MACD, ATR14), signals, trade plan, backtest, screen. `python idx.py` runs the offline self-check.
- `ml.py`: ML layer. `HistGradientBoostingClassifier` on 17 scale-free features (returns, EMA distances, RSI, MACD, ATR, volume ratio, 20d-high distance, liquidity, equal-weight market context). Label = the mode's trade plan from that day ends in net profit (reuses `idx.outcome`). Walk-forward validation: 4 blocks of 120 trading days, train only on earlier dates with a `hold`+1 day gap. `python ml.py` = leakage check on random walks (AUC must stay ~0.5).
- `app.py`: Streamlit dashboard; sidebar for mode, capital, allocation, liquidity, universe. Loads 5y data; shows walk-forward table, avg AUC, edge verdict (AUC >= 0.53), ml_prob column, top ML picks.

## Trading rules (user decisions, 2026-11-14)
- User trades daily and swing. Two modes:
  - swing: close>EMA20>EMA50, RSI 45-70, MACD hist >0 and rising, volume >1.2x 20d avg. Stop 1.5 ATR, target 2R, max hold 10 days.
  - daily: close > prior 20d high, close in top 25% of day range, volume >=2x avg, green day. Stop 1 ATR, target 1.5R, hold 1 day.
- Stop loss never more than 5% below entry (user max loss 5%). Prices rounded to IDX tick sizes, 1 lot = 100 shares.
- Fees: buy 0.15%, sell 0.25%.
- Universe: hardcoded LQ45-like list in `idx.UNIVERSE`; update each LQ45 review.
- Backtest: enter next open after signal, stop checked before target when both touched (conservative).

## ML results (2026-11-14, 46 stocks, 5y)
- swing: walk-forward AUC ~0.50 = no edge; app tells user to ignore ml_prob.
- daily: AUC 0.54-0.56 every block; top-10% win ~43% vs ~34% base, avg net return still ~break-even after fees.
- Ideas not done: IHSG index + foreign flow features, sector features, probability calibration, longer history.
