# m07 prediction markets: favourite-longshot harvest (STATUS)

Last update: 2026-09-24 11:55 UTC. **COMPLETE. Verdict: NO EDGE.** The report is in README.md.

## Done
* DEV data: Kalshi 10,133 markets with snapshots (k04 DEV stopped at 10,501 of 20,423 after a 429; that is a random prefix of the seeded shuffle).
  Polymarket 6,825 markets (all of DEV).
* DEV analysis (a02): Kalshi has 0 of 112 cells positive after fees. Polymarket's best cell is H=72 [0.85,0.97], +2.2%/bet with CI (0.3, 4.0),
  but capacity-limited it earns 2.7%/yr at K=$100k vs SPY 29%.
* PREREG.md frozen before any TEST outcome was seen.
* TEST data (outcome-blind, seeded): Kalshi 6,000 markets -> 5,335 with snapshots. Polymarket 5,000 of 1,151,457 eligible markets
  (p03_test_sample.py) -> 2,954 with snapshots.
* TEST run ONCE (a03 TEST ... frozen):
  * Polymarket: 485 events, +0.24c/contract with CI (-2.0, +2.35), ret +0.26%/bet with CI (-2.2, +2.6). At 2x costs, -1.06%/bet.
    The sample sim CAGR is 1.8% vs SPY 18.0%.
  * Kalshi: 38 events, -2.1%/bet; with no filters, 255 events at -6.7%/bet, CI (-10.6, -3.2).
* a04 calibration DEV vs TEST: out/calib_frozenH.csv, out/calib_DEV_TEST.png. README.md written.
* Disk: raw poly_parts/ deleted (it duplicated poly_markets_20240701_20260901.csv.gz). The data folder is now about 660 MB.

## Next steps
None. An optional follow-up would be maker (limit-order) execution, which needs historical order books that we do not have.
