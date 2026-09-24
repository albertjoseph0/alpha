# m05 insider clusters: STATUS (Round 5b resume)

## State found at resume (2026-09-24)
* Scripts 01-06 existed; 01 had fetched SEC form345 2006q1-2023q4 compact files; old `events.parquet`
  only covers 2006-01..2007-09 (built mid-fetch; left untouched). No prices, results or PREREG existed.

## Done
1. `01b_fetch_sec_fn.py`: all quarters 2006q1-2026q1 (latest SEC set; 2026q2 = 404), new
   `quarters/{yq}_pfn.parquet` (code-P rows + footnote text + remarks + AFF10B5ONE). No errors. Zips deleted.
2. `03b_build_events.py` -> `events_v2.parquet` (16,301 events 2006-2026q1), `purchases_v2.parquet`
   (561,715 clean officer/director purchases), `event_members_v2.parquet` (112,662 cluster purchases).
   Fix vs 03: skip "stale" clusters where no filing on F is in the window.
3. 05_backtest.py now reads `*_v2` files (TAG) and uses a 20-day lag on SEC shares outstanding;
   06_analyze.py caches `prepared_v2.pkl`.

## Running / next
* `04b_fetch_prices.py` (yfinance -> px/, splits/, px_missing.txt; log prices.log). Re-run to resume.
* `08_jev_score.py` (Jev on 28,039 unique anonymized footnote states, ~13.6M tokens ~ $0.6;
  -> jev_purchase_v2.parquet; log jev_score.log). Re-run is free (disk cache).
* Then: `07_dev.py prep` (price matching, cache), `07_dev.py rules`, `07_dev.py ml` -> dev_results/.
* Then PREREG.md (A and A+B), 09_test.py once, README.md.
