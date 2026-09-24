# Interim notes: m03 and m04 (agents stopped at the container restart; not resumed in round 5b)

## m03: convex trend with long SPX calls. Dev evidence is negative.
Results are in `m03_convex_trend_calls/grid_dev.csv` and `yearly_dev.csv`. DEV is 1990–2007, with Black–Scholes
pricing on a VIX/VIX1Y/SKEW-derived surface and a 2% option spread.
* Across all 36 grid settings (premium budget X ∈ {0.1, 0.2, 0.3}, moneyness, roll 1/3/6/12 months), none beat SPY.
  The best, X=0.3 at-the-money with a 12-month roll, made 9.3% CAGR vs SPY's ~10.3% (−0.9 pts). With implied vol
  +2 or +4 points it made 7.0% and 5.0%.
* Losing years (1992, 1994, 2005, 2007) come from option decay while the trend was up but flat. Gains come in
  strong bull years (1995–97).
* No test run was made, and it isn't warranted, because DEV shows no edge.

## m04: Noah-effect tail barbell. The pricing check passed; the backtest was never run.
`chain_check*.csv` compares the calibrated skew models with a real SPX option chain (CBOE delayed quotes,
2026-09-22, 329–987 puts):

| put moneyness | real mid | SSVI model / real mid | "linz" model / real mid | bid-ask spread / mid |
|---|---:|---:|---:|---:|
| < −35% | 12.1 | 1.43–1.51 | 0.93 | 5% |
| −35% to −25% | 22.5 | 1.70–1.73 | 1.04 | 3.4% |
| −25% to −15% | 42–44 | 1.62–1.70 | 1.14 | 2.4% |
| −15% to −5% | 88–94 | 1.32–1.48 | 1.16 | 1.5% |

* **Correction to an earlier orchestrator statement.** I said far out-of-the-money puts trade at "5–15×
  the model price with ~100% spreads". That was read from the first rows of the file, which are the shortest
  expiry (24 days) and the deepest strikes, where quotes are a few cents wide. Across the whole chain,
  the calibrated "linz" model prices puts within about ±15% of real mid prices, and spreads are 1.5–5% of
  mid. The barbell is **not** disproven: the agent built and validated a pricer but never ran the
  backtest.
* Next step: resume m04 with the "linz"-calibrated pricer and run DEV 1990–2007, then TEST 2008+.
