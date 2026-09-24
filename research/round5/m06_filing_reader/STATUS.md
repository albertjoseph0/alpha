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

## DEV results (done; details in PREREG.md)
- results_dev_full.csv / ic_dev_full.csv: all price/text models negative OOF IC (logit price -0.19 t-3.9), -13..-15 pts/yr vs SPY.
- results_dev_jev.csv / ic_dev_jev.csv (Jev subset 2020-01..2021-06): all negative; price+jev IC -0.13 (t -1.95).
- Fixed before prereg: label overlap with day0_x (labels now start at the open after entry); prices_pre.parquet (s04c) so 2020 events have momentum.
- PREREG.md WRITTEN (frozen).
## TEST full DONE (ran once, ~11:36 UTC): results_test_full.csv / ic_test_full.csv
- 45 months 2023-01..2026-09, SPY 21.8%/yr. Verdict strategy logit price+dict+finbert 14.0% net (-7.8 pts), IC -0.002 (t -0.07).
  logit price 20.7% (-1.1), +dict 16.1%, +finbert 15.2%; control EW 13.1%. All test ICs |t| < 1.1. -> NO EDGE.

## Running
- s07 Jev TEST sample, CUT to 2023-06-30 because the gateway ran at ~0.5 calls/s (prereg allows this):
  `JEV_THREADS=6 python s07_jev.py 2023-06-30 2022-10-01` -> DATA/jev_features_2022-10-01_2023-06-30.parquet (log s07_c.log)
- s10_leak_probe.py (Jev forward-question probe, 300 dev + 300 test-2023 events) -> RES/leak_probe.csv (log DATA/s10.log)

## Next
- when s07 ends: `s06_events.py` then `s08_model.py test jev` (once) -> README.md
