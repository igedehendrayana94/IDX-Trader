# IDX-Trader

Small dashboard that screens Indonesian (IDX) stocks and gives buy candidates with stop loss, target and lot size. Orders are placed manually in the Stockbit app (Stockbit has no official API; unofficial token access was rejected by the user).

## Stack
- Python 3.13 venv in `.venv/` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`)
- Data: yfinance daily bars, `CODE.JK`, unadjusted (matches Stockbit prices). Public data only.
- UI: Streamlit (`.venv/bin/streamlit run app.py`, port 8501)

## Files
- `idx.py`: fetch, indicators (EMA20/50, RSI14, MACD, ATR14), signals, trade plan, backtest, screen. `python idx.py` runs the offline self-check.
- `app.py`: Streamlit dashboard; sidebar for mode, capital, allocation, liquidity, universe.

## Trading rules (user decisions, 2026-11-14)
- User trades daily and swing. Two modes:
  - swing: close>EMA20>EMA50, RSI 45-70, MACD hist >0 and rising, volume >1.2x 20d avg. Stop 1.5 ATR, target 2R, max hold 10 days.
  - daily: close > prior 20d high, close in top 25% of day range, volume >=2x avg, green day. Stop 1 ATR, target 1.5R, hold 1 day.
- Stop loss never more than 5% below entry (user max loss 5%). Prices rounded to IDX tick sizes, 1 lot = 100 shares.
- Fees: buy 0.15%, sell 0.25%.
- Universe: hardcoded LQ45-like list in `idx.UNIVERSE`; update each LQ45 review.
- Backtest: enter next open after signal, stop checked before target when both touched (conservative).
