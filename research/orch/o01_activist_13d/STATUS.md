# o01 activist 13D + Jev: STATUS

Agent o01 took over from the orchestrator on 2026-09-24 (Jev budget "o01" = $3). Folder research/orch/o01_activist_13d/,
data data/orch/o01_activist_13d/. No git commits (orchestrator commits).

## Pipeline (run in this order; every step is resumable / cached)
1. `s01_list.py` -> filings.csv (EFTS listing of initial SC 13D / SCHEDULE 13D, 2013-01..2026-08). Subject = first CIK.
2. `s01b_allhits.py` -> all_hits.parquet (initial + amendments, from cache; for point-in-time filer-history features).
3. `s03_prices.py` -> px_close/px_vol/px_split.parquet, px_missing.txt (yfinance, current tickers; chunks in px_chunks/).
4. `s05_events.py` -> events.parquet + survivorship_counts.csv. Event = subject CIK x file_date, later initial 13Ds on the
   same subject within 182 days dropped. Entry = close of first trading day after file_date. Investable = raw price >= $2
   and 20d median dollar volume >= $250k.
5. `s02_text.py` -> texts.jsonl.gz (Item 4 + percent of class) for filings of investable events only.
6. `s06_features.py` -> panel.parquet (feature sets A no-text, B +keywords; representative filing per event).
7. `s04_jev.py score` -> jev.parquet (question set V1); `s04_jev.py probe` -> probe.parquet (leakage probe).
8. `s07_dev.py` (to write): DEV walk-forward, 3 nested feature sets, rules by Jev intent; then PREREG.md; then s08_test.py once.
9. README.md (report + verdict).

Shared code: `common.py` (paths, cost model by liquidity bucket, drift-weighted calendar-time backtest, stats).

## Design decisions (fixed before looking at any returns)
- DEV = filings 2014-2019, TEST = filings 2020+ (sealed until PREREG.md exists).
- Costs one-way by 20d median dollar volume: >=$50M 5bp, $10-50M 15bp, $2-10M 30bp, $0.5-2M 60bp, <$0.5M 100bp; +25bp if
  price < $5. 2x costs also reported.
- Portfolio: buy-and-hold weights, new position = NAV/max(N_active, 20), cash-funded then pro-rata trims; exits to cash.
- Jev question set V1 = the one in s04_jev.py (intent 8-way choice, hostility score, letter_sent, undervalued, agreement,
  specific_demand on anonymized Item 4; filer_type on filer names only). Question sets tried: V1 only (so far).

## Progress log
- 03:00 s01_list.py (started by orchestrator) still running, at 2020-04. s03 updated to also save splits (raw price filter).
- Checked: EFTS display_names lists the subject first. s02 extraction works on samples; some filings have no Item 4
  text in the main document (cover pages only) and are dropped (coverage to be reported).

## Next step
Wait for s01 to finish (`pgrep -af s01_list`; log data/orch/o01_activist_13d/s01.log), then run s01b, s03, s05, s02, s06, s04.
