# r2:fractal_mom_joseph: 49-industry 12-1 momentum on the "Joseph" part of the path

## Bottom line
The question for this angle was whether fractal refinements of the momentum signal add robust value over plain 12-1 momentum on the 49 industries. **They mostly do not.**
* **Vol or path-length normalisation hurts in every window.** This covers ruler efficiency at 5-day and 21-day rulers, and trading-time z-scores. The damage is largest in the early window, at 1.5–3 points.
* **Jump filtering ("Joseph without Noah") is the only refinement that does not lose.** It is statistically indistinguishable from plain momentum: top-third holdings overlap 93%, and the signals have a cross-sectional rank correlation of 0.975.

The submitted strategy is the jump-winsorised version. It keeps the one economically clean fractal idea: remove the uninformative Noah component. Expect it to behave like the baseline in the holdout.

## Rule
On the first trading day of each month, the strategy does the following for every `i49_*` industry that has at least 250 valid days in the last 252:
1. Winsorise each daily log return at ±3σ. Here σ is that industry's daily log-return std over the 252 days ending the previous day.
2. Sum the clipped returns over the 12-1 window, days t−251 … t−21.
3. Hold the top third of industries, equal-weighted and fully invested. Positions drift until the next rebalance.

There are four parameters: 12-1 window, top third, 250/252 validity, and 3σ. The first three are the baseline's. 3σ is the conventional outlier cut, fixed a priori. Nothing is fitted, and the run is causal and audit-clean.

## Results (harness CLI; result_*.json)
| window | **this** | baseline 12-1 mom (49) | buy & hold |
|---|---:|---:|---:|
| dev 1950–99 | **17.62%** | 17.58% | 13.40% |
| dev_a 1950–74 | 14.95% | 15.08% | 9.42% |
| dev_b 1975–99 | **20.20%** | 19.98% | 17.53% |
| early 1932–49 | 15.93% | 15.97% | 10.52% |

It beats buy & hold in every window by 2.7 to 5.5 points. Against the baseline it is +0.04, −0.13, +0.22 and −0.04 points, which is a tie: the standard error is about 2%/yr.

## Sources
* **Noah vs Joseph effects:** Mandelbrot & Hudson, *Misbehavior of Markets*, ch. X (research/extracted, pp. ~225–234). Round 1 (strategies/mf_spectrum) found that the jump part of a 12-month move carries no cross-sectional information.
* **Ruler / divider length:** L(ε) ∝ ε^(1−D), ch. VII pp. 157–159 (the mf_spectrum port).
* **Trading time:** ch. XI pp. 235–250, and strategies/multifractal_vol.

## Everything evaluated (12 CAGR configurations × 4 windows; `research/evals.log`)
All configurations use the 12-1 window, the top third and monthly rebalancing on i49. Scripts are in `research/signals.py` and `research/run_grid.py`.

| config | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| mom (baseline, reproduced exactly) | 17.58 | 15.08 | 19.98 | 15.97 |
| eff5: ruler efficiency X/L₅ | 17.17 | 14.55 | 19.72 | 14.48 |
| eff21: ruler efficiency X/L₂₁ | 16.82 | 14.11 | 19.44 | 13.22 |
| tt1: trading-time z, X/√Σr² | 17.04 | 14.55 | 19.43 | 13.09 |
| tt5: trading-time z, 5-day returns | 16.93 | 14.20 | 19.58 | 12.92 |
| **jw3: winsorise at 3σ (final)** | 17.62 | 14.95 | 20.20 | 15.93 |
| jr3: remove days beyond 3σ | 17.59 | 14.14 | 20.98 | 15.59 |
| jw2: winsorise at 2σ | 17.62 | 14.73 | 20.40 | 14.33 |
| noah3: jump part only (diagnostic) | 13.92 | 11.17 | 16.55 | 13.50 |
| mom + eff5, rank average | 17.32 | 14.55 | 20.01 | 15.26 |
| mom + tt1, rank average | 17.33 | 14.43 | 20.15 | 14.33 |
| jw3 + (−D), where D is the divider dimension from 5- and 21-day rulers | 16.43 | 13.28 | 19.50 | 12.35 |

Beyond the CAGR grid, I ran one rank-IC study (`research/ic.py`). It computes monthly ICs against the next month's return, taken after the execution lag, both raw and as the residual after removing momentum ranks. I also ran one holdings-overlap check and the 4 CLI runs of the final strategy. **Total: 12 strategy configurations.**

Rank-IC means, with t-statistics in parentheses (early / dev_a / dev_b):
* **mom:** .037 (2.3) / .089 (5.6) / .065 (3.9).
* **Noah part:** .009 / −.001 / −.004. Given momentum: −.004 / −.013 (−1.4) / −.019 (−1.7). The jump part carries nothing, as in round 1.
* **Joseph part given momentum:** .012 (1.0) / .039 (4.1) / .032 (3.1). The sign is positive in every period, but the gain is too small to change the top third much.
* **Ruler efficiency and trading time given momentum:** about 0 in the early window, and positive only in dev_a. That is the low-volatility tilt, and it costs CAGR.
* **Divider dimension D (vol-free smoothness):** weakly negative in all periods (t −0.4 / −2.6 / −1.7). Mixing it in at half weight diluted momentum and hurt CAGR.

## Why the round-1 smoothness result did not transfer
On 12 industries, dividing by path length (≈ volatility) helped slightly. On 49 industries, cross-sectional volatility dispersion is much larger, so normalisation mostly becomes a tilt toward low-vol industries among the winners. That tilt lowers CAGR. The loss is largest in 1932–49, even though the rank IC of volatility is negative there. So the damage comes from magnitude: a few high-vol winners with large payoffs that rank ICs do not capture. I have not decomposed this further. Breadth made plain momentum strong enough that the refinements have little left to add.

## Risks
* **Selection:** I picked the best-looking non-losing variant from 12. Its edge over the baseline is +0.04 points in dev, which is pure noise. Treat its holdout expectation as equal to plain 49-industry 12-1 momentum.
* **Momentum risk is inherited in full:** crashes in sharp rebound years (1975-style), market-like drawdowns of −40% or worse, and no timing defence.
* **Tail sensitivity:** winsorising discards large positive days. If future industry trends arrive mainly through jumps (for example, news-driven sector re-ratings), the filter will lag plain momentum.
* **Data:** some i49 series start late or have gaps. The validity rule excludes an industry until it has 250 valid days in the last 252.
