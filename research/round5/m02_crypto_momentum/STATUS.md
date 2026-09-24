# m02 crypto momentum: STATUS

## Done
- fetch.py/prep.py/backtest.py/run_dev.py written by the previous instance (before the restart).
- symbols_all.txt (3710 spot symbols, 735 *USDT incl. delisted; LUNAUSDT/FTTUSDT present), spy.csv.
- Raw monthly 1d klines: ~235/735 USDT pairs were done at restart; the fetch was resumed (5b) with lower concurrency.
  Archive's last monthly file = 2026-08 (so data end = 2026-08-31).

## In progress
- `fetch.py` running (log: data/round5/m02_crypto_momentum/fetch2.log). It is idempotent: rerun skips cached raw/*.csv.

## Next steps
1. When the fetch finishes -> klines_1d.parquet; run prep.py -> close/qv/trades.parquet, instruments.csv.
2. run_dev.py > dev_results.txt (DEV 2018-2021 only).
3. Write PREREG.md, then run the TEST once (2022-01-01 -> 2026-08-31).
4. README.md with the full report and verdict.
