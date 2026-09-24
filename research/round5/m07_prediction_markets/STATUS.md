# m07 prediction markets: favourite-longshot harvest (STATUS)

Last update: 2026-09-24 11:35 UTC (round 5b, second resumed instance)

## State
* DEV data: done. Kalshi DEV has candles for 10,501 of 20,423 sampled markets. k04 DEV died on a 429 and was not
  resumed, and 10,133 markets have usable snapshots. Polymarket DEV is complete (6,825 markets).
* DEV analysis: done. a01 DEV kalshi was rerun and a02_dev.py rerun (out/artifacts_DEV.txt, grid_*, calib_*).
  * Kalshi: 0% of grid cells have positive mean P&L after fees. The least bad cell is H=1 [0.95,0.97], ret -0.5%/bet.
  * Polymarket: H=72 [0.85,0.97] gives ret +2.2%/bet, CI (0.3%, 4.0%). Only 3% of cells have CI > 0, so this is a multiple-testing winner.
    Capacity is tiny: at K=$100k the capacity-limited return is 2.7%/yr vs SPY 29% (out/eval_poly_DEV_frozen.txt).
  * Kalshi 0.97-0.99 anomaly (the favourite wins only 93%): an artifact of spread > 20c books (fake 0.99 asks), not an edge.
* PREREG.md: written and frozen (primary = Polymarket H=72 [0.85,0.97]; secondary = Kalshi H=1 [0.95,0.97]).
* TEST downloads (outcome-blind, running in the background at 11:25):
  * `k04_candles.py TEST 6000` -> kalshi_candles_TEST.pkl.gz (log k04_TEST2.log)
  * `p03_test_sample.py 5000` -> poly_sample_TEST / poly_hist_TEST.pkl.gz (log p03_TEST.log). The universe is 1,151,457
    markets, so the sampling fraction is 5000/1151457 = 0.004342.
* Code changes this instance: p03_test_sample.py (new); a01 reads Polymarket ids as str; a03 takes FRAC as argv[7]
  and computes capacity-limited returns, and in TEST the Polymarket base has no outcome filter;
  lib_fl clips the Kalshi fee at 2x costs (it went negative when ex > 1).

## Next steps (exact)
1. When both downloads finish: `a01_snapshots.py TEST`
2. `a03_eval.py TEST poly 72 0.85 0.97 frozen 0.004342` and `a03_eval.py TEST kalshi 1 0.95 0.97 frozen`, run ONCE.
3. Calibration table for TEST (L.calib on the TEST snapshots) and README.md with the verdict.
