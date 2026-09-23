# fractal:mfspec_ruler_rotation

## Result (harness CLI, causality audit passed)
| window | CAGR | benchmark B&H Mkt | EW industries |
|---|---:|---:|---:|
| dev 1950–99 | **+16.43%** | +13.40% | +13.54% |
| dev_a 1950–74 | +12.98% | +9.42% | +9.91% |
| dev_b 1975–99 | +19.81% | +17.53% | +17.13% |
| pre-dev check 1935–49 (research sim, same engine) | +10.72% | +9.85% | +10.44% |

Runtime of the full dev run: **1.5 s**. Turnover is about 3.8×/yr, which costs about 0.2%/yr at 5 bp.

## The final rule
On the first trading day of each month, the strategy scores every industry by the signed ruler efficiency of its log-price path over the last 250 days, holds the top 4 of 12 equally weighted, and stays fully invested. It holds and drifts between rebalances.

    eff = X_250 / L_5(250),   X_250 = sum of log returns over 250 days,
    L_5 = path length measured with a 5-day ruler (sum of |5-day returns|, averaged over the 5 phases).

There are three parameters (250-day outer ruler, 5-day inner ruler, top 4). All three are conventional choices and none was tuned: 1 year, 1 week, one third of the universe. Nothing is fitted.

## Hypothesis and sources
* **Fractal (ruler/divider) dimension of a price path** (Mandelbrot & Hudson, `misbehavior_of_markets_mandelbrot.txt` PDF pp. 157–159, where coastline length depends on the ruler; box counting in the Notes, pp. 320–321). The measured length of a rough curve scales as L(ε) ∝ ε^(1−D). This gives L(250)/L(5) = |X|/L_5 = 50^(1−D): the ratio is near 1 for a smooth trend (D→1) and small for a rough, space-filling path (D→2). Signed by direction, it ranks industries by how smooth ("Joseph-like", ch. IX–X) their trend is.
* **Noah vs Joseph** (book ch. X, a Joseph almost-trend breaks as a Noah discontinuity; heresy 3, returns concentrate in a few days). I split each 12-month move into jump days (|r| > c·σ, low local Hölder exponent) and regular days. The jump ("Noah") part has **zero** cross-sectional IC in every period (e.g. −0.006/−0.005/−0.001 for 1931–49/1950–74/1975–99). All of the trend information is in the regular part. A ruler-length normalisation measures that regular persistence.
* **Weekly, not daily, inner ruler.** Bouchaud 2026 (`mandelbrot_origins_of_econophysics.txt` p. 5) warns that microstructure mimics multi-scaling, and REVIEW §5 documents stale-price autocorrelation of +0.13 to +0.29 in the dev period. A 5-day ruler keeps the roughness estimate off the scale where that bias lives.

## What was tested and failed: the multifractal spectrum itself
All estimators are in `mfcore.py` and are causal, built on prefix sums. The research scripts are in `research/`, and `research/evals.log` lists every backtest.
* **Estimator sanity.** Full-sample λ² from the MRW log-volatility covariance slope (Borland et al., `dynamics_of_financial_markets.txt` pp. 9–11) is 0.025 (1926–49), 0.028 (1950–74) and 0.006 (1975–99). The first two match the paper's λ² ≈ 0.03 (p. 6). λ² from ζ_q curvature (p. 6, q = 1..4) is 0.05–0.14, inflated by the fat tails of a few crash days. This is Bouchaud's finite-sample warning (p. 5) in practice.
* **Information beyond realized volatility** (monthly partial regressions, Mkt, controlling for ln RV21 and ln RV252). For forward returns, λ²(log-cov), λ²(ζ curvature), the cascade slope Var[ln σ_τ] vs ln τ (p. 8), h = ζ₂/2, the local Hölder exponent and the 126-day box dimension all have |t| < 2 in 1975–99. Their signs flip between 1931–49, 1950–74 and 1975–99. For forward vol, the λ² estimators had t ≈ −2 to −3 in 1950–74 but ≈ 0 in 1975–99. **Conclusion: the spectrum and intermittency estimates carry no robust information beyond plain RV.** Their correlation with RV is low (0.1–0.3), so they measure something different, but that something did not predict.
* **Cross-section (12 industries).** Rank ICs of λ²(cov), λ²(ζ), h₂, Hölder, kurtosis and the fraction of jump days are all ≈ 0 with inconsistent signs. Only path-roughness/trend measures work: the 252-day box dimension has IC −0.015/−0.050/−0.039, and signed efficiency +0.067/+0.064/+0.091, which is higher than 12-1 momentum.
* **Market timing (weekly, cash when the measure is above its trailing-10y 80th percentile).** RV63 filter 9.00% dev. λ²(cov) 9.39% (dev_a 4.45%). λ²(ζ, q ≤ 2) 12.65%. RV & λ² 11.04%. Hölder-burst filter 10.67%. Trend OR calm cascade 12.37%. Every one is below B&H at 13.40%. On 1935–49 the λ² filters beat B&H (10.55% / 10.40% vs 9.85%), so their sign is unstable.
* **Turbulence as a concentration switch** (equal-weight all 12 industries when turbulent, instead of the top 4). On the efficiency core: RV 15.95%, λ²(cov) 15.20%, λ²(ζ) 16.28%, versus 16.10% without a switch. On the momentum core: 15.50 / 15.31 / 16.00 versus 16.06. These are noise-level changes, so no switch was kept.
* **Core variants.** 12-1 momentum top 4: 16.06% (pre 9.79%). Daily-ruler efficiency: 16.10% (pre 11.78%). 126+252 rank average: 16.23% (a 13.66, b 18.66). Literal multi-ruler divider-dimension regression, sign(X)·(2−D): 13.43%, because it discards the trend's size and the regression D is poorly behaved (median 2.44). Inverse-vol weights within the top 4: 15.79%. Top 6: 15.20%. I chose the plain weekly-ruler top 4 on simplicity and stability across dev_a, dev_b and pre-dev, not on the dev maximum (the variants lie within ±0.3 points, which is well inside the ~2%/yr standard error).

## Number of dev evaluations
* 35 research backtests on dev data (with the harness `engine.simulate`), logged in `research/evals.log`. This includes 2 sanity baselines and 5 benchmark-like references. 11 of them also reported the 1935–49 period.
* 3 harness CLI runs of the final strategy (dev, dev_a, dev_b).
* Also run: exploratory IC and regression studies (research/explore_features.py, explore_xs.py, explore_noah_joseph.py).

## Known risks (why it could fail out of sample)
* **This is essentially vol-normalised industry momentum.** Efficiency ≈ trailing Sharpe ratio, with 0.8 cross-sectional rank correlation to 12-month momentum. It inherits momentum crashes: sharp rebounds after bear markets, when the losers rally. That risk is plausibly larger in 2000–2026 than in 1950–99. The turbulence switch that should guard against it did not help in dev, so it was not added.
* The 1935–49 result (+10.72% vs B&H +9.85%, EW +10.44%) shows the edge is much smaller in turbulent eras.
* It is concentrated in 4 industries and fully invested, with no market-timing defence against 50% drawdowns.
* Industry definitions and composition drift over time (e.g. BusEq and Telcm after 1995).
