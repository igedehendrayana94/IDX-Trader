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
- Bilingual UI (Indonesia default, English); all strings in `texts.py` (`T`, `COND` plain-language condition names, `COLS` column label+help, `GLOSSARY`); sidebar toggle. Indonesian strings follow KBBI forms and the Jutif term rules (`Jurnal Jutif Template/JUTIF-SLR-Guide.md` §6.2): italic *swing*, *stop loss*, *backtest*, *walk-forward*, *machine learning*; "uji historis (*backtest*)"; "jeda" not "tertunda" (not in KBBI); Indonesian number format (1.000,50) via `num()`. Add every new string to both languages.

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
- IHSG features added 2026-11-14 (`^JKSE` via yfinance: ret5, ret20, dist to EMA50, 20d volatility, stock ret20 minus IHSG ret20). Sidebar toggle, default on. Walk-forward: daily AUC 0.55 -> 0.54, swing 0.505 -> 0.492; top-10% avg return in daily slightly better (-0.24% -> -0.06%). Within noise: overlaps the equal-weight market features.
- Foreign flow: idx.co.id API is behind a Cloudflare challenge (403 for curl and for a Playwright browser); not bypassed. User downloads 'Ringkasan Saham' Excel per day into `data/foreign/` (gitignored, date YYYYMMDD in file name). `idx.load_foreign` reads 'Kode Saham', 'Foreign Buy', 'Foreign Sell'. Features fnet5/fnet20 = net foreign shares over 5/20 days divided by normal volume. Used by the model only when >= 60 trading days of files exist.
- Ideas not done: sector features, probability calibration, longer history.

## UI/UX for novice traders (2026-11-14, ui-ux-pro-max skill)
- Streamlit native only, theme in `.streamlit/config.toml` (primary teal #0E7C66: neutral, never read as gain/loss).
- Answer first: 3 KPI cards (buy ideas today, IHSG + change, "use ML model?" Ya/Tidak), data date as caption.
- Tabs: Rekomendasi | Prediksi ML | Semua saham | Panduan. Material icons only, no emoji; meaning never by colour alone.
- Sidebar shows only language, trading style (with captions) and capital; the rest is in "Pengaturan lanjutan".
- Buy card: metrics (buy price, SL with -%, target with +%, lots), Rp cost and max loss as % of capital, checklist of conditions met, ML line only when model has edge, 5y history, warning when the rule's history on that stock is negative, one primary button "Buka di Stockbit".
- No signal: info box ("not buying is valid") + "Hampir memenuhi syarat" cards (missing exactly one condition).
- ML tab: when no edge, the probability ranking is hidden inside the advanced expander.
- Guide tab: 6-step how-to (incl. Stockbit Auto Order), glossary, risk box.
- Check: AppTest over id/en x swing/daily with forced signals (temporary script, not committed).
