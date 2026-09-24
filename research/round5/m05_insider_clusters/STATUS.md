# m05 insider clusters: STATUS (Round 5b resume)

## State found at resume (2026-09-24)
* Scripts 01-06 exist (from the killed round-5 instance). 01 had fetched SEC form345 quarters 2006q1-2023q4
  (compact P/S parquet + `_trail` price files); 2024q1 zip downloaded but not processed; raw zips of
  earlier quarters were deleted, so FOOTNOTES were never kept.
* `events.parquet` (old, do not touch) only covers 2006-01..2007-09 (it was built while 01 was still
  running). No prices (`px/`) were ever fetched. No results, no PREREG.
* Latest SEC data set available: 2026q1 (2026q2 = 404).

## Plan / next steps
1. `01b_fetch_sec_fn.py`: re-download every quarter 2006q1-2026q1 once, write missing compact files
   and NEW per-quarter purchase+footnote files `quarters/{yq}_pfn.parquet`; delete zips.
2. `03b_build_events.py` -> `events_v2.parquet`, `purchases_v2.parquet` (full 2006-2026q1).
3. `04b_fetch_prices.py` -> `px/`, `splits/`, `bench.parquet`.
4. DEV (2006-2015) analysis of A; Jev scoring of purchase footnotes (B); PREREG; TEST once; README.
