# m02 crypto momentum: STATUS

## Done
- fetch.py/prep.py/backtest.py/run_dev.py written by the previous instance (before the restart).
- symbols_all.txt (3710 spot symbols, 735 *USDT incl. delisted; LUNAUSDT/FTTUSDT present), spy.csv.
- Raw monthly 1d klines: ~235/735 USDT pairs were done at restart; the fetch was resumed (5b) with lower concurrency.
  Archive's last monthly file = 2026-08 (so data end = 2026-08-31).

## Data DONE (5b)
- All 735 *USDT pairs fetched (122 files imported read-only from m09's identical raw_spot via import_m09.py;
  fetch.py fixed to URL-quote the non-ASCII symbol). klines_1d.parquet 2017-08-17 -> 2026-08-31.
- prep.py (5b fixes): also excludes BULL/BEAR (3x BTC tokens), WBTC/WBETH/BETH, KGST/U (stables), SPYB (tokenized SPY);
  back-adjusts 5 token redenominations (COCOS, DREP, SUN, BNX, QUICK). 660 instruments, 196 ended before data end.
  LUNA (2022-05) and FTT (2022-11) present as delisted instruments. Output: prep_output.txt.

## DEV DONE (dev_results.txt, dev2_results.txt, dev_grid.csv, dev_attribution.csv)
- Canonical DEV 2018-21: 68.1% CAGR vs BTC 36.4%, SPY 17.3%; 2x costs 59.5%; maxDD -75%; delisting modes identical (no hits).
- Ex-2021 (2018-20): 20.1% vs BTC 29.3%; BTC+SMA100 control 44.3%. Weekly excess vs BTC t=0.58; negative without best 5 weeks.
- Only 6-19 USDT pairs existed in 2018 (universe = everything). Capacity: 39% at $1M, 7% at $10M (dev).

## PREREG.md written (frozen = backtest.DEFAULT) before the TEST.

## TEST DONE (run once; test_results.txt, test_diag.txt)
- 2022-01 -> 2026-08: canonical -41.9% CAGR (2x costs -44.5%) vs BTC +11.3%, SPY +12.2%; maxDD -93%; 887 trades.
  delist->zero is identical (0 hits). BTC+SMA100 control 4.4%; EW top-30+filter -31.9%.
- Cross-sectional spread (top-5 mom minus top-30 EW, next week) in TEST: -0.97%/wk, t=-2.17. No bug found:
  prices were checked and the worst days are real pump-and-dumps.

## COMPLETE: README.md written, verdict NO EDGE. No further steps. Do not rerun the TEST with changes.
