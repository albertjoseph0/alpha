# m04 tail barbell: pre-registration (written 2026-09-24, before any TEST-period run)

No backtest, benchmark or cross-check index has been run or inspected on dates after 2007-12-31 for this
strategy. Exceptions, both from the previous instance: the 2026-09-22 SPX chain used for the pricer check, and the
PPUT replication in pput_check.py, whose output covers 2008-2026. That check tests the pricer on 1-month 5%-OTM
puts and does not use the barbell rule. I saw its 2008-2026 figures, but none of the barbell's.

## Frozen rule
- Equity sleeve: SPY total return (SPY adjusted close; before 1993-01-29, ^SP500TR minus 9.45 bp/yr).
- Put sleeve, rolled on the first trading day of every month at the close:
  - Sell the whole existing tranche at the model bid.
  - Buy SPX puts with strike K = S_t x (1 - **0.30**), rounded to 5 index points.
  - Expiry: the 3rd Friday of calendar month m + **4** (about 4.5 months at purchase, sold at the next roll with about 3.5 months left).
  - Premium spent at the ask: **1%/12** of NAV (annual gross outlay 1% of NAV).
- Monetize: if the tranche's model mark at the close of t-1 is at least **5x** its purchase cost, sell it at the close of t.
  The proceeds go to equity, and a fresh tranche is bought at once under the same strike, expiry and budget rule.
- Everything not in puts is in the equity sleeve. There is no leverage, and the maximum loss on the put sleeve is its premium.
- Config file: `frozen_config.json` = {"depth": 0.30, "tenor": 4, "budget": 0.01, "monet": 5}.
- Selection: highest DEV base-case CAGR out of 24 configurations (grid_dev.csv). **0 of 24 beat SPY on DEV.**
  The selected rule is the least-bad one: it has the smallest net premium bleed (0.22%/yr) and made -0.24 pts/yr vs SPY.

## Pricing and costs (identical to DEV)
- Mark: the "linz" skew model, recalibrated every day to VIX, VIX3M, VIX6M, VIX1Y and the trailing 21-day mean of SKEW
  (surface_s21.pkl). From 2008 all four VIX-family indices are published, so no proxies are needed in TEST.
- Base case: half-spread 2.5% of premium, and 1 bp on equity flows.
- 2x cost: half-spread 5%.
- SSVI (expensive) case: SSVI rho=-0.7 surface, half-spread 2.5%; also SSVI with 5%.
- Tick case: half-spread at least 0.05 points, and ask at least 0.10 points.
- rawskew case: calibrated to the raw daily SKEW.

## Benchmarks
100% SPY (primary). Also 97% SPY + 3% T-bills (monthly rebalance), and the same crash-rebalancing idea with plain cash:
97/3 SPY/bills, with all cash moved into SPY when SPX is at least 20% (and, in a variant, 30%) below its 252-day high,
and rebuilt at a new 252-day high.

## TEST
2008-01-02 to 2026-09-22 (the last date in the data), started fresh at NAV 1. Run exactly once:
`python evaluate.py test`.

## Success criterion (base case, vs 100% SPY, TEST CAGR)
- MOONSHOT CANDIDATE: at least +20 pts/yr, and above SPY in the x2 and SSVI cases.
- REAL BUT SMALLER: above 0 in base, x2 and SSVI, and at least +1 pt/yr in base.
- Otherwise: NO EDGE.

## Also reported, descriptive only (declared now; no reselection)
- All 24 grid configurations on TEST (grid_test.csv).
- The canonical Universa-like configuration (30% OTM, 2-month, 3.3%/yr, 5x monetize), which was grid row 17 on DEV and made -1.63 pts/yr.
- Yearly returns, and CAGR excluding 2008, excluding 2020, and excluding both.
- The VXTH and PPUT real-index comparison over 2006/2008-2026.
