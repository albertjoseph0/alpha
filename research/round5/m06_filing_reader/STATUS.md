# m06 filing reader: STATUS (Round 5b resume, 2026-09-24 ~11:30 UTC)

## Done
- s01 universe: point-in-time S&P 500 intervals (data/.../sp500_pit_intervals.csv, READ-ONLY for others) + ticker_cik.csv
- s02: events_8k202.csv = 14,579 8-K Item 2.02 filings 2019-10..2026-09 while the firm was an S&P 500 member
- s03: texts_all.jsonl.gz complete (all 14,579). s04: prices.parquet (53 delisted tickers missing; stress-tested).
- s05: FinBERT + LM scored for all 14,579 events (sc_part000..029.parquet).
- s07 Jev (base run): 3,173 events 2020-01..2021-06 in jev_features.parquet ($0.76 spent of $15).
  Jev scoring was NOT extended to all events (time); Jev comparison uses a sample (see below).
- The old run_s07_loop.sh was stuck (another agent's shell matched its pgrep pattern) and was killed.

## Design decision (Jev sample)
- Full-sample comparison: price / +LM / +FinBERT on all DEV (2020-22) and TEST (2023+) events.
- Identical-events Jev comparison: all four sets (price, +LM, +FinBERT, +Jev) on Jev-covered events only:
  DEV = 2020-01..2021-06 (cached), TEST = 2023 filings (+2022-10..12 for the first rebalance's eligible set).

## Running
- s07 Jev sample run: `python s07_jev.py 2023-12-31 2022-10-01` -> DATA/jev_features_2022-10-01_2023-12-31.parquet
  (log DATA/s07_b.log; resumable via Jev cache; just re-run the same command if killed)

## Next
- s06_events.py (merges all jev_features*.parquet) -> s08_model.py dev -> PREREG.md -> s08 test ONCE -> leakage probe -> README.md
