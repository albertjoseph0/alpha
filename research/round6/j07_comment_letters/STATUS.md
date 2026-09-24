# j07 SEC comment letters + Jev: STATUS (updated 03:12 UTC)

## Done
- s00_universe.py: m11 PIT S&P 500 month-end membership (2011-12..2026-09) + j01's PIT (ticker, year) -> CIK map
  (frozen copy in DATA/ticker_year_cik.csv) -> DATA/universe_monthly.csv (804 CIKs, ~504 names/month).
- Key data fact: for UPLOAD/CORRESP the EDGAR 'Date Filed' is the LETTER date. The public dissemination date is
  the daily-index date, which equals the date on the submission header line (`<SEC-DOCUMENT>... : YYYYMMDD`).
  Verified on 4 letters (Apple UPLOAD dated 2015-05-19 was disseminated 2015-10-05).
- s01_daily_index.py (full daily-index crawl) STOPPED after ~50 days of 2012Q1 (DATA/daily/2012Q1.partial.csv),
  because the shared SEC limiter gives this agent ~0.4 req/s. That partial is kept as a validation sample for
  header dates.
- s01b_quarterly.py -> DATA/qindex.csv: UPLOAD 9,300 / CORRESP 7,757 rows for ever-member CIKs (letter dates).

## Running (resumable: rerun the same command; it skips accessions already in the output)
- `s02_letters.py 20110701 20191231 letters_text_dev.jsonl.gz` (5,387 letters, log DATA/s02_dev.log)
- `s02_letters.py 20200101 20261231 letters_text_test.jsonl.gz` (1,762 letters, log DATA/s02_test.log;
  TEST texts are data only until PREREG.md is written)

## Next
- s03_events.py: validate header dates vs DATA/daily/2012Q1.partial.csv; build release events (cik, dissem date),
  PIT member filter at month-end before dissemination; no-text + keyword features.
- Jev questions (questions.py), leakage probe, DEV model (walk-forward), overlays, PREREG, TEST once, README.
