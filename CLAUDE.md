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

## Stockbit-style look (2026-11-14)
- Reference: stockbit.com (screenshot + CSS colours). Style only: no Stockbit logo or name as branding; app stays "IDX Trader".
- Tokens: brand green #00AB6B / red #EE4A49 for sparklines and accents; text and buttons darkened to #007A4D / #C62F2E (WCAG 4.5:1; #00AB6B on white is 2.98:1). Text #333333, muted #6B6B6B, lines #EDEDED. Font Nunito Sans (free, close to Proxima Nova). Theme in `.streamlit/config.toml`.
- `ui.py`: HTML parts (CSS tokens, watchlist row with 30-day SVG sparkline, change "+94 (+1,78%)" with sign always shown, order-ticket rows, stats strip). `python ui.py` = self-check incl. HTML escaping of user codes.
- Header = IHSG watchlist row + stats strip. Buy card = watchlist row + BELI chip + order ticket + reasons + full-width "BELI {code} DI STOCKBIT" button. "Semua saham" = watchlist with "3/4 syarat" chips; dataframe moved into "Tabel lengkap" expander.
- Company names hardcoded in `idx.NAMES` for the default list.

## Entry/exit timing (2026-11-15)
- `timing.py`: IDX session clock (WIB; pre-open 08:45-09:00, sesi 1 09:00-12:00 / Fri 11:30, sesi 2 13:30 / Fri 14:00 - 15:50, pre-close 15:50-16:00), next trading day (weekends only: IDX holidays NOT included), `schedule()` buy day + sell-by date, `exit_check()` hold/sell for a position, `drop_unfinished()` removes today's partial bar before 16:15 WIB (bug fix: a mid-session bar was treated as a closed signal day). `python timing.py` = self-check.
- Exit rules for a position: stop/target from the same plan (ATR of the day before buying); order: stop hit -> SELL, target hit -> SELL take profit, days >= hold -> SELL (time), swing close < EMA20 -> CONSIDER SELLING, else HOLD; on the deadline day during market hours -> SELL TODAY at pre-close.
- UI: header status line (market phase + next open), buy card "Kapan bertindak" ticket (order in pre-opening at limit price, Auto Order SL/TP, daily check after 16:15, sell-by date), tab "Posisi saya" (form, saved to `data/positions.json`, gitignored; delete asks for confirmation), guide box with IDX hours.
- ML stays gradient boosting (best fit for tabular indicators); exit advice is rule-based, not ML.

## External libraries evaluated (2026-11-15)
- `tradingview_ta` 3.3.0 (unofficial TradingView wrapper, repo archived 2024-06): works for IDX with screener "indonesia", exchange "IDX", daily and 15m; close matches yfinance. Snapshot only (no history) so it cannot be backtested: shown as a second-opinion line on buy cards and positions (`idx.tv_ratings`, cached 5 min, returns {} when unreachable). Not used in ML or signals.
- pandas-ta 0.4.71b0 (the Data-Analisis repo is a fork of pandas-ta): 10 extra indicators (ADX, DI diff, MFI, OBV slope, CMF, BB %B, Stoch K, Williams %R, ROC10, NATR) tested as ML features. Walk-forward AUC swing 0.492 -> 0.500, daily 0.540 -> 0.542: noise. Not adopted (would add numba for no gain).
- Trader skill repos (trader-skill, day-trader-skill, claude-trading-skills): all US-only (Nasdaq/NYSE lists, NY session, SEC/FMP/Alpaca); none runs on IDX as-is. Ideas worth porting: regime traffic light, risk-based sizing + risk gate, opening-range-breakout day mode, trade journal (not built yet, waiting for user choice).

## Four features from the trader skill repos (2026-11-15)
- `risk.py`: regime traffic light (`regime_series`): IHSG vs rising EMA50, IHSG distribution days (down >= 0.2% on higher volume, last 25 sessions), breadth (% of list above EMA50). green / yellow (half size) / red (gate blocks new buys). 5y check: red-regime signals were worst (swing avg -1.33% vs green -0.73%; daily -1.19% vs -0.98%) but ALL regimes negative after fees. On 2026-11-13 regime = red.
- Sizing: `idx.size_lots` = capital x risk% / (loss per share incl. fees x 100), capped by max allocation; used in `idx.plan`. Sidebar risk slider 0.5-2% (default 1%).
- Risk gate (`risk.gate`, PASS/BLOCK): regime, lots >= 1, R:R >= 1.5, cash vs open positions, max open (5), max buys/day (3), daily loss limit (3%), 3-loss streak pauses the next trading day, ORB entry window (before 14:30). BLOCK disables the Stockbit button and hides "I bought it".
- `orb.py`: opening range breakout on yfinance 5m bars (~60 days, delayed 10-15 min). Range 09:00-09:15, entry first 5m close above high before 14:30, stop = range middle (<= 5%), target 1.5R (1R barely clears 0.4% fees), exit at stop/target or closing price. Time Machine replay: 1,059 trades / 46 stocks / 60 days: 28% win, avg -0.64% per trade. Tab "Day trading" auto-refreshes every 5 min in market hours; live cards include a don't-chase rule (> 0.5R above entry = skip).
- `journal.py`: JSON storage (`data/positions.json`, `data/journal.json`, gitignored), close position -> journal row (P/L Rp, %, R), stats (win rate, expectancy, profit factor, avg R, loss streak), ISO-week digest, coaching notes. Tab "Jurnal".
- Positions now store stop/target when added via "I bought it"; `timing.exit_check` uses them; ORB positions hold 1 day.
- Checks: `python risk.py|orb.py|journal.py|timing.py` self-checks; AppTest end-to-end (red blocks, green buy -> position -> close -> journal; simulated live ORB session with temporary scripts, not committed).

## Data source decision (2026-11-16)
- Keep yfinance (delayed ~10-15 min). Realtime IDX needs a paid licensed feed (IDX/ICE; TwelveData, Oanor unverified); swing/daily trade on daily closes so delay does not matter, and ORB replay lost money anyway. Revisit only if ORB gets an edge.
- `app.py` clears the `load()` cache when Yahoo returns nothing, so a transient failure retries on next rerun instead of showing "Data tidak tersedia" for 1h.
- Live prices (2026-11-16): `load_live` (cache 5 min) adds today's unfinished yfinance bar to watchlist rows, the IHSG header and position checks (`with_live`); signals, regime and ML still use closed days only. Header reads "Sinyal dari penutupan <date> · ... · Harga pukul HH:MM WIB (tertunda ±15 menit)". `auto_refresh` fragment reruns the whole page every 5 min while the market is open. `load`/`load_ihsg` take a `day` cache key so the new closed bar appears at 16:15 WIB.

## Book knowledge test (2026-11-16, ~/Downloads/Saham)
- Read: RLA/Illusix modules (trading rules, Trend Template TV script, screeners, signal-table manual, trend-reversal notes), Minervini "Think & Trade Like a Champion", Pro Trader RL paper (ESWA 2024, Donchian signal + RS rank + ATR(N) features), Galen Woods price patterns, trend-following and indicator books. Scanned PDFs (Edianto Ong, Ryan Filbert swing, Fibonacci Satrio Utomo, Workbook TA, Raymond Budiman, Graham ID ed.4, Linda Lee) have no text layer; no OCR installed, not read.
- Not usable for ML: fundamental screeners (PE/PBV/ROE/F-score need point-in-time history; yfinance has only today's values -> lookahead), bandarmology (needs broker summary), Stockbit auto-click scripts (not learning material).
- Walk-forward, 44 stocks, 5y, IHSG on. Groups added to the 22 base features: trend template (SMA50/150/200 distance, SMA200 22d slope, 52w low/high distance, 7-criteria score), relative strength (IBD RS, cross-sectional RS rank + 10d MA, RRG ratio/momentum vs IHSG), VCP (ATR vs 63d ago, 10d/60d range, 10d/50d volume, Donchian-low distance), breadth (% up today, % above EMA50). Swing AUC 0.492 -> 0.492-0.498 (no edge); daily 0.540 -> 0.535-0.548, top-10% avg still negative. Within noise: not adopted.
- Same rules as fixed filters with book thresholds on the app's own plan outcome (net of fees): momentum filters made it worse (swing signal -1.03% avg -> TT 7/7 -1.46%, RS rank >= 0.8 -1.36%); best was VCP tight + volume dry-up on swing signals -0.37% (n=116, sign flips by year). Nothing positive. Likely reason: the books pair these entries with their own exits (Minervini 7-8% stop, trail/close below MA20; trend following holds months), not a 10-day 2R plan. Untested: book entries with book exits.
- Experiment scripts kept out of the repo (scratchpad).
