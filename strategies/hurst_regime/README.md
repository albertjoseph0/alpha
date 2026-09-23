# fractal:hurst_xs_persistence — Joseph effect / long memory

**Final dev CAGR: +16.17%** (dev_a 1950–74: +12.95%, dev_b 1975–99: +19.48%).
Benchmarks: buy & hold +13.40% (dev_a +9.42%, dev_b +17.53%); equal-weight industries +13.54%.
Runtime of the final dev run is 5.4 s single-threaded, and the causality audit passes.

**Bottom line:** once the Lo critique is taken seriously, rolling H does **not** add measurable value
beyond a plain trend rule on this data. The CAGR comes from cross-sectional
persistence of industry *relative* returns (industry momentum). H chose that design and acts
as a safety valve, but it never switches off in 1950–99.

## Hypothesis and sources
* H measures persistence: H > ½ means runs continue and H < ½ means they reverse
  (Mandelbrot & Hudson, `misbehavior_of_markets_mandelbrot.txt` pp. 215–216, 222–223, 229).
  Estimators: R/S (Notes pp. 325–327), plus the shuffle comparison that separates Joseph from Noah (p. 230).
* There is no consensus on H values. Lo (1991) showed that R/S confounds short memory with long memory, and the book's lesson is
  "never publish any result based on a single tool" (p. 220). Persistent-looking patterns can
  be pure chance (heresy 8, pp. 272–275).
* Returns are nearly uncorrelated, while volatility has long memory (Borland et al.
  `dynamics_of_financial_markets.txt` pp. 3–5, facts (i)–(ii); REVIEW.md §5). The stale-price
  autocorrelation in dev-era index data biases H upward (REVIEW.md §5).

## What the research found (scripts in `research/`, all on `load_dev()`)
1. **Estimator check** (`00`). With 5 years of weekly data (N=260), the sd of Ĥ is 0.04–0.09. AR(1) with
   ρ=0.2 inflates R/S, DFA and VT by +0.04–0.07 (Lo's critique). Lo's V is robust to this but has low power.
2. **Levels** (`01`, `04`). Over 1926–99, raw weekly H is 0.50–0.57, only marginally outside the
   shuffled-surrogate bands, and Lo's V is inside the short-memory region for 12/13 assets. H of |r| is
   0.70–0.86, a strong Joseph effect in *volatility*. Pre-whitening pulls market-wide H down to
   ≈0.50–0.54. **Relative** returns (industry − Mkt) are more persistent: weekly and monthly H ≈ 0.51–0.62, with
   monthly lag-1 autocorrelation of +0.04 to +0.12, and several industries sit beyond the shuffle band.
3. **Does rolling H predict trend payoff?** (`02`). Pooled over 13 assets for 1930–99, corr(H, next-month
   trend payoff) lies within ±0.07 for R/S, DFA, VT, Lo and H(|r|). The sign flips across
   estimators, horizons and sub-periods. **No.**
4. **Strategy tests** (harness `simulate`, identical frictions). The table gives dev CAGR, with dev_a and dev_b in brackets:

| variant | dev (dev_a / dev_b) |
|---|---|
| market 12m trend long/cash | 11.77% (9.94 / 13.64) |
| market 200-day MA (daily) | 12.43% (11.33 / 13.55) |
| industries 12m TSMOM, each 1/12 | 12.07% (10.55 / 13.61) |
| market trend filter only when H>½ (weekly / pre-whitened / Lo H) | 11.92 / 10.71 / 12.15% |
| **top-4 industries by 12m relative strength (A)** | **16.17% (12.95 / 19.48)** |
| A with fBm predictor β(H)·r (contrarian when H<½), 5y / 10y H | 15.38 / 16.02% |
| top-4 by H alone | 13.17% |
| A, winners need raw relative-H>½ (C) | 16.68% (13.48 / 19.96) |
| C with pre-whitened H / Lo H / cross-sectional-median H | 16.20 / 16.74 / 15.43% |
| C-Lo plus dual momentum (defensive) / H-gated dual momentum | 16.03 / 16.31% |
| C-Lo with inverse-vol weights | 16.47% |
| **final (A with a pooled 10y relative-H gate)** | **16.17% (12.95 / 19.48)** |

5. **Placebo (shuffle) test** (`06`). Real H in filter C beat 60 time-shifted H series on dev
   (0/60 ≥ real). However, the grid of 6 lookback × K settings gives C − A = −0.20 to +0.51%, mean +0.17%, which is noise.
6. **Pre-1950 regime check** (`10`, 1932–49, data never used for any choice). A 15.90%, C-Lo 15.08%,
   C-raw 14.37%, dual momentum 11.92%, market trend filter 8.81% (buy & hold 14.12%). The per-industry H filter
   and the defensive switches **hurt** out of period. So they were dropped.

## Final method (`strategy.py`, `hurst.py`)
Every 21 trading days (anchored at the first data row):
* Pooled persistence H\* is the mean over the 12 industries of avg(R/S Anis–Lloyd-corrected, DFA-1,
  variance-time). Each is estimated on the last 520 weekly *relative* returns (industry − Mkt).
* If H\* > 0.5, the strategy holds the 4 industries with the highest 252-day relative log return, at 1/4 each. Otherwise
  it holds all 12 industries at equal weight. It has no cash, shorts or leverage.

Parameters: 21-day cadence, 10-year H window, 12-month lookback, top 4, threshold 0.5 (the
Brownian value, so it isn't fitted). The gate is on for 100% of 1950–99 anchors (H\* 0.55–0.57 by decade)
and for 89% of 1936–49, where it cost 0.6% versus plain A. It is a mechanism-based safety valve: if
cross-sectional persistence disappears, the strategy stops trend-following and holds equal weight. Its dev value is unproven.
Turnover is about 4 per year, which costs about 0.2%/yr.

## Evaluation count
* 44 strategy variants, each scored on dev, dev_a and dev_b. The log is in `research/eval_log.txt`.
* 60 placebo runs and 8 pre-1950 checks. These were used for testing, not selection.
* 3 harness CLI runs of the final strategy (dev, dev_a, dev_b).

The final strategy was not the best dev scorer: C-Lo scored 16.74%. It was chosen for robustness.

## Known risks
* The edge is industry momentum, and it has no timing or defensive layer. The strategy is fully invested in 4 industries and takes
  the full equity drawdown (max drawdown −47% over 1932–49 in the pre-1950 check). Industry momentum can crash at sharp
  market reversals, and its strength post-2000 is uncertain.
* The H gate is untested in dev because it was always on. Post-2000 short-lag autocorrelation turns
  negative, which biases weekly H down. The gate could then switch to equal weight, whose dev CAGR is close to the market's, even if momentum still works.
* The 16.17% dev CAGR has a standard error of about 2%/yr. The 2.8% margin over buy & hold is only about 1.4 SE.

No packages were installed.
