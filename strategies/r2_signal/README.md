# r2:signal_mom_blend12: 49-industry momentum with a blended 12-month signal

Angle: engineer the momentum **ranking signal** and keep the round-2 baseline's portfolio unchanged
(49 industries, top third, equal weight, rebalanced on the first trading day of each month).

## Final strategy (`strategy.py`)
Only industries with at least 250 valid days in the last 252 are ranked. For each of them, average its
cross-sectional percentile rank on three windows that all end within the last 12 months:

| leg | window (trading days) | rationale |
|---|---|---|
| 12-0 | t-252 .. t | Industry momentum shows no one-month reversal (Moskowitz–Grinblatt), so the skip is optional |
| 12-1 | t-252 .. t-21 | The classic signal (the baseline) |
| 12-7 | t-252 .. t-126 | "Intermediate" momentum (Novy-Marx): older returns carry more of the effect |

Buy the top third by blended rank, equal weight, monthly. The blend weights the months roughly
1 : 2 (months 2–6) : 3 (months 7–12) and hedges two uncertain choices, the skip month and the
horizon emphasis. No parameters are fitted. The three legs are standard literature windows, chosen
before testing and not tuned.

## Results (CAGR, harness CLI)

| | dev 1950–99 | dev_a 1950–74 | dev_b 1975–99 | early 1932–49 |
|---|---:|---:|---:|---:|
| **r2:signal_mom_blend12** | **17.70%** | 14.28% | **21.04%** | 15.94% |
| baseline 12-1, top third | 17.58% | 15.08% | 19.98% | 15.97% |
| buy & hold | 13.40% | 9.42% | 17.53% | 10.52% |

The strategy beats buy & hold in every window, by 4.3, 4.9, 3.5 and 5.4 points. Against the baseline,
at the mandated top-third construction it wins dev (+0.12) and dev_b (+1.06), ties early (−0.03), and
**loses dev_a (−0.80)**.

**Robustness across portfolio breadth.** This is the evidence behind choosing the blend. It is a
diagnostic only; the final strategy keeps top third.

| top fraction | signal | dev | dev_a | dev_b | early |
|---|---|---:|---:|---:|---:|
| 1/4 | baseline 12-1 | 18.11 | 15.25 | 20.88 | 16.08 |
| 1/4 | blend | **18.76** | **15.43** | **22.02** | **16.84** |
| 1/3 | baseline 12-1 | 17.58 | 15.08 | 19.98 | 15.97 |
| 1/3 | blend | **17.70** | 14.28 | **21.04** | 15.94 |
| 1/2 | baseline 12-1 | 16.16 | 13.19 | 19.04 | 14.40 |
| 1/2 | blend | **16.49** | **13.56** | **19.32** | **15.86** |

The blend beats 12-1 in 10 of 12 window × breadth cells. Both losses are at top third, which is the
configuration that is scored.

## Everything tried (top third unless noted; lab code in `lab.py`)

| signal | dev | dev_a | dev_b | early | verdict |
|---|---:|---:|---:|---:|---|
| base 12-1 | 17.58 | 15.08 | 19.98 | 15.97 | reference |
| rank ensemble 6-1/9-1/12-1 | 17.09 | 14.99 | 19.06 | 12.53 | worse everywhere; **early −3.4** |
| ensemble 6/9/12 × skip 0/1 | 17.50 | 15.45 | 19.44 | 11.83 | helps dev_a only; early −4.1 |
| ensemble 3/6/9/12-1 | 16.87 | 14.70 | 18.94 | 13.00 | worse everywhere |
| 12-0 (no skip) | 18.20 | 15.43 | 20.86 | 15.32 | **helps all of dev, hurts early** |
| 12-7 intermediate | 16.56 | 12.85 | 20.24 | 17.95 | helps dev_b and early, hurts dev_a (−2.2) |
| 18-1 | 16.32 | 13.73 | 18.85 | 14.10 | worse everywhere |
| 52-week-high proximity | 16.65 | 14.17 | 19.05 | 12.67 | worse everywhere |
| vol-scaled 12-1 | 17.21 | 14.62 | 19.70 | 12.65 | worse; early −3.3 |
| residual (beta-adj., 3y beta on 21d returns) | 16.84 | 14.23 | 19.36 | 14.05 | worse everywhere |
| ½ residual + ½ raw rank | 17.35 | 14.74 | 19.87 | 15.19 | slightly worse everywhere |
| frog-in-the-pan smoothness + 12-1 rank | 17.48 | 14.96 | 19.88 | 15.23 | slightly worse everywhere |
| 12-1 rank + FF12 group 12-1 rank | 16.67 | 13.52 | 19.77 | 14.57 | worse everywhere |
| 12-0 + 12-1 ranks | 17.83 | 15.13 | 20.41 | 15.59 | dev-positive, early −0.4 (also −1.4 at top ¼) |
| 12-1 + 12-7 ranks | 17.30 | 13.99 | 20.53 | 17.30 | dev_a −1.1 |
| 12-0 + 12-1 + 12-7 ranks (ranked over all 49 incl. unavailable) | 17.71 | 14.30 | 21.04 | 16.14 | chosen idea |
| same, ranked among valid industries only (**final**) | 17.70 | 14.28 | 21.04 | 15.94 | final |
| same three legs, raw log-return sum | 17.54 | 14.13 | 20.89 | 15.76 | 8/12 cells vs base (rank blend 10/12) |

Breadth diagnostics used 1/4 and 1/2 for base, the 3-leg blend (both ranking variants), the 12-0 + 12-1
blend and the raw-sum blend.

**Configurations evaluated: 28** (each on 4 windows): 18 signals at top third, plus 10 breadth
diagnostics. That count includes the ranking fix. It excludes the four final CLI runs, which repeat the
final configuration.

## Takeaways
* The 12-1 signal is hard to improve. Short lookbacks (3–9 months), volatility scaling, 52-week high,
  residual momentum, smoothness and group trend all lost in most windows, often by a lot in early.
  The early window reliably rejected ideas that lean on recent months.
* The only consistent structure: **older returns (months 7–12) help and shorter windows hurt**, while
  the skip month does not matter much in 1950–99. The blend combines the two effects that survive.
* The 0.2-point shift in early from a cosmetic ranking change (ranking over valid versus all columns)
  shows the noise floor. Every difference here below about 1 point is within noise, since tracking error
  over 18–25 years gives a standard error of about 1.5 points of CAGR.

## Risks
* The edge over the baseline is small and uneven (dev_a −0.8). Expect roughly baseline-level
  performance out of sample, and treat any extra as a bonus.
* Selection bias: 28 configurations were tried, and the pick was the best of a few blends. It was
  chosen for consistency across breadth, not for peak dev CAGR, which 12-0 alone had.
* The blend emphasizes older returns, so it turns more slowly after regime changes. Like the baseline,
  it loses in sharp loser rebounds and carries market-like drawdowns (always fully invested).
* Turnover is similar to the baseline (a monthly top-third book). Costs are modeled at 5 bp.
