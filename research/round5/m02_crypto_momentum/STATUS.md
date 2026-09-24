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

## Next steps
1. When the fetch finishes -> klines_1d.parquet; run prep.py -> close/qv/trades.parquet, instruments.csv.
2. run_dev.py > dev_results.txt (DEV 2018-2021 only).
3. Write PREREG.md, then run the TEST once (2022-01-01 -> 2026-08-31).
4. README.md with the full report and verdict.
