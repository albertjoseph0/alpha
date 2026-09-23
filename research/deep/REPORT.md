# Deep dive: robust trend-switched momentum (`strategies/deep_trend_switch/`)

Done by the orchestrator, without subagents. It starts from the only tradeable strategy that beat SPY
out of sample in round 3 (`r3_options`, whose single 210-day trend switch was fragile in development).

## Protocol (fixed before iterating)
* Iterate only on ETF 2000–2015 (`etf_dev_a` 2000–07, `etf_dev_b` 2008–15), plus an independent
  1965–1999 proxy history (`build_proxy.py`: US market, 49 industries, synthetic 5y and 10y
  Treasuries built from Yahoo yields, gold-miners index). The 2016–2026 holdout had already been
  seen once in round 3, so it is not used for iteration. The frozen final gets one run on it.
* "Definitively beats SPY" means:
  (1) beats SPY in 2000–07, 2008–15 and both proxy halves;
  (2) robust across neighbouring settings;
  (3) block-bootstrap P(CAGR > SPY) ≥ 90%;
  (4) beats SPY in the single final 2016–26 run.
* Every configuration is logged in `evals.log`. The grids are in `grid_*.csv`.

## What was learned
* Diagnosis: the edge comes from (a) offense-mode momentum riding global and commodity booms, and
  (b) switching to defense in bear markets (2001–02, 2008). The costs are slow re-entry (2009) and
  whipsaws or commodity reversals (2011).
* The original 210-day switch was the luckiest trend length. Across 126–252 days, 2000–07, 1965–81
  and 1982–99 beat SPY at every length, but 2008–15 passes only at 210–231.
* Fixes tried and rejected, because they don't improve 2008–15 robustly: per-asset trend gate,
  volatility caps (15–30%), and partial de-risking floors (25–100%). Full switching is monotonically
  best. The one change kept is an ensemble of four trend lengths (6, 8, 10 and 12 months), which
  removes the single-parameter luck.

## Final: `deep:trend_switch_ens`

| period | strategy | SPY / market | excess | P(beat), block bootstrap |
|---|---:|---:|---:|---:|
| 1965–1981 (proxy) | 17.4% | 7.05% | +10.3 | |
| 1982–1999 (proxy) | 20.2% | 17.89% | +2.3 | |
| 1965–1999 (proxy) | | 12.49% | +6.1 | 0.998 |
| 2000–2007 (ETF) | 13.23% | 1.55% | +11.7 | |
| 2008–2015 (ETF) | 6.65% | 6.46% | +0.2 | |
| 2000–2015 (ETF dev) | 9.87% | 3.98% | +5.9 | 0.958 |
| **2016–2026 (ETF holdout, one run)** | **16.08%** | **14.99%** | **+1.1** | 0.56 |
| **2000–2026 (ETF, all)** | **12.27%** | **8.27%** | **+4.0** | **0.914** |

Max drawdown 2000–2026: −39.4% vs −55.2% for SPY. It beat SPY in 15 of 27 calendar years.
Neighbourhood: 53% of 36 nearby settings beat SPY in all four development windows. The failures
are all in 2008–15, where the median setting is a tie.

## Verdict
* **Beats SPY in every period tested**, across 61 years and two independent datasets, with smaller
  drawdowns. Aggregate evidence is strong: P = 0.998 on 1965–99 and 0.914 on 2000–26.
* **Not definitive on recent data alone.** The edge was +0.2 in 2008–15 and +1.1 in 2016–26, and
  2016–26 by itself is statistically a coin flip (P = 0.56). The edge has shrunk as the US large-cap
  market came to dominate. Its biggest wins are bear markets (2001–02, 2008, 2022) and commodity
  booms (2005–07, 2025).
* Further iteration would fit 2008–15 or the already-seen holdout, so development stops here. The
  honest next test is forward paper trading.

## Forward Monte Carlo (`monte_carlo.py`)
The simulation builds 10,000 future paths per horizon. Each path is stitched together from chunks
of real history (strategy and SPY taken on the same days, average chunk length 3 months), which
keeps volatility clustering and fat tails. Costs are included. Results are in `monte_carlo_*.csv`.

| resampled from | horizon | strategy CAGR, median [p10, p90] | SPY CAGR, median | P(beat SPY) | worst-decile max DD (strategy / SPY) | P(DD < −40%) (strategy / SPY) |
|---|---|---|---:|---:|---|---|
| 2000–2026 | 5y | 12.4% [2.4, 23.3] | 8.8% | 72% | −37% / −47% | 6% / 19% |
| 2000–2026 | 10y | 12.3% [5.1, 19.9] | 8.6% | 80% | −42% / −53% | 14% / 38% |
| 2008–2026 | 5y | 11.8% [2.8, 21.8] | 12.0% | 52% | −35% / −47% | 3% / 20% |
| 2008–2026 | 10y | 11.8% [5.3, 18.8] | 11.6% | 53% | −39% / −52% | 9% / 38% |

**What it shows.** The drawdown advantage holds in both sets of history. The return advantage does
not. Taken over 2000–26, the strategy beats SPY in about 80% of 10-year futures. Taken over 2008–26
alone, its expected return equals SPY's (P ≈ 53%), but it gets there with about 13 points smaller
worst-case drawdowns and half the chance of a −40% crash. Its CAGR spread is also slightly narrower
than SPY's. Whether it *out-earns* SPY depends on the next decade looking more like 2000–07 (bear
markets, commodity booms) or like 2010–2021 (US large-cap dominance).
