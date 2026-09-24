# j05 IPO quality — STATUS (update after every milestone)

Pipeline (run from this folder with /home/user/alpha/.venv/bin/python; all incremental / re-runnable):
1. s01_index.py — EDGAR form.idx 2009Q3..2026Q3 → data/round6/j05_ipo_quality/index_rows.csv  **DONE**
2. s02_candidates.py — first 424B4 per CIK after an S-1/F-1 → candidates.csv (3625 non-SPAC-name)  **DONE**
3. s03_fetch.py — 424B4 primary doc → txt/<acc>.txt.gz (raw HTML not cached). **RUNNING in background**
   (log: data/.../fetch.log, ~16 docs/min, sorted by date; restart just re-runs and skips done files)
4. s04_extract.py — IPO check, SPAC/units flags, ticker, price, underwriters, keyword features, sections
   → meta.csv, sections.jsonl.gz. **FROZEN** (changing it changes Jev states → cache misses).
5. s05_prices.py — yfinance per IPO (cover ticker, then SEC current ticker; first bar within -3..+20 days of 424B4)
   → prices/<acc>.parquet, price_map.csv (incremental).
6. s06_edgar_status.py — EDGAR submissions JSON: Form 25/15, merger filings, last periodic → edgar_status.csv.
7. s07_jev.py v1 START END — Jev question set v1 (jevq.py) → jev_v1.jsonl; `s07_jev.py v1 2010-01-01 2018-12-31 leak` = probe.
8. s08_panel.py → panel.parquet (entry = open of bar 26 after listing, exit = open of bar 278; outcomes vs SPY).
9. s09_backtest.py dev|test [cost_bp] — walk-forward logistic (a/b/c), rules, portfolio sim, survivorship scenarios.

Decisions so far
- Costs: 40 bp per side base (IPO small/mid caps), 80 bp at 2x.
- Survivorship: yfinance has ~28% of 2010 IPOs (Yahoo purges delisted/acquired). No free delisted-price
  source found (stooq blocked; HF datasets are current-only or gated). Handled by scenarios: survivors-only,
  missing = -50%, missing = -100%, and "refined" (EDGAR: failed in hold → -100%, acquired in hold → 0%,
  alive past exit → dropped). Also a survivorship-free label: failure (Form 25/15 w/o merger) within hold.
- Jev cost ≈ 8k tokens/doc ≈ $0.00033/doc.

Next step: wait for fetch of DEV (2010–2018) docs; then s04 → s05 → s06 → s07 (DEV) → s08 → s09 dev.

## Note (orchestrator, 11:38 UTC)
The orphaned s03_fetch.py was stopped because its agent had ended at the usage limit. Re-run it to resume; SEC responses are cached.
