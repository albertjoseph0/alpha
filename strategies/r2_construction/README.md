# r2:construct_rank5_stag4: portfolio construction for 49-industry momentum

## Idea
The signal stays fixed: plain 12-1 momentum on the 49 industries. Only the step from signal to portfolio changes.
1. **Hold the top fifth, not the top third.** That is k = round(n/5), about 10 of 49 names.
2. **Weight linearly by rank among the winners.** The best name gets weight k and the k-th gets 1, then the weights are normalised. This gives about 8 effective names. A name enters and leaves at a small weight, which acts as a soft buffer at the cutoff.
3. **Split the book into four staggered tranches.** Each tranche is refreshed monthly, on trading day 0, 5, 10 or 15 of the month. The portfolio is the equal average of the four. Every tranche stays monthly, so the signal stays fresh, and the rebalance-day timing luck averages out.
4. **Stay fully invested, long only.** There are no caps and no timing.

No document citations. Economic reasoning:
- Momentum's cross-sectional return spread sits in the extreme winners, so tilting toward the top ranks raises expected return.
- The 49-industry universe is broad enough that about 8 effective names still diversify industry noise. This is the fundamental-law trade-off between skill and breadth.
- Momentum decays over a few months, so a stale portfolio loses return.

## Parameters (3, all structural)
- FRAC = 1/5
- rank weighting
- 4 tranches at day offsets 0/5/10/15

The signal (252/21 lookback and skip, eligibility of ≥250 valid days out of 252 plus the last 5 days valid) is inherited unchanged from the baseline.

## Results (harness CLI, result_*.json)
| | dev 1950–99 | dev_a 1950–74 | dev_b 1975–99 | early 1932–49 |
|---|---:|---:|---:|---:|
| **r2:construct_rank5_stag4** | **19.62%** | **16.43%** | **22.73%** | **17.69%** |
| baseline (eq-wt top third, monthly) | 17.58% | 15.08% | 19.98% | 15.97% |
| buy & hold | 13.40% | 9.42% | 17.53% | 10.52% |

It beats both the baseline and buy & hold in every window. The margin over the baseline is +2.0, +1.4, +2.8 and +1.7 points.

## Sensitivity surface (CAGR %, dev / dev_a / dev_b / early)
Configurations are monthly on day 0 and equal-weighted unless noted. The full log is in `grid_log.jsonl`, produced by `research.py`.

**Number of holdings (equal weight):**

| holdings | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| top 1/2 | 16.16 | 13.19 | 19.04 | 14.37 |
| top 1/3 (baseline) | 17.58 | 15.08 | 19.98 | 15.93 |
| top 1/4 | 18.11 | 15.25 | 20.88 | 15.99 |
| top 1/5 | 18.58 | 15.43 | 21.67 | 16.67 |
| top 1/7 | 19.85 | 16.13 | 23.53 | 16.07 |
| top 1/10 | 19.51 | 15.94 | 23.04 | 19.09 |
| top 1/15 (3 names) | 18.72 | 16.11 | 21.20 | 17.50 |

- On 49 industries, concentration helps in every window, including early. This is unlike 12 industries.
- The surface peaks around 1/7–1/10 and turns down at 3 names.

**Weighting, top third:**

| weighting | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| rank | 18.51 | 15.54 | 21.39 | 16.61 |
| inverse vol, 63d | 17.33 | 15.01 | 19.54 | 14.86 |
| inverse vol, 252d | 17.40 | 15.12 | 19.57 | 15.05 |
| Kelly-style μ/σ² (cap 2× equal weight) | 18.31 | 16.10 | 20.41 | 14.60 |

- Rank weighting over the top 1/2 scores 17.56 / 14.61 / 20.43 / 15.64.
- Rank weighting over all names scores 15.38 / 12.15 / 18.54 / 14.24.
- Inverse vol and Kelly both hurt on early. Down-weighting volatile winners removes return.

**Rank weighting with the top-k cutoff, monthly:**

| cutoff | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| 1/4 | 19.02 | 15.77 | 22.20 | 16.74 |
| 1/5 | 19.37 | 16.02 | 22.64 | 17.00 |
| 1/10 | 19.34 | 16.30 | 22.28 | 18.57 |

**Slower rebalancing, overlapping monthly tranches and hysteresis all lose CAGR.** Results for the top third:

| variant | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| quarterly, offset 0 | 17.41 | 14.13 | 20.64 | 16.25 |
| quarterly, offset 1 | 16.84 | 13.85 | 19.24 | 15.49 |
| quarterly, offset 2 | 17.31 | 14.06 | 19.74 | 15.77 |
| bi-monthly, offset 0 | 17.35 | 14.30 | 20.27 | 15.63 |
| bi-monthly, offset 1 | 17.56 | 14.40 | 20.17 | 16.26 |
| 3 overlapping monthly tranches (Jegadeesh–Titman) | 17.17 | 14.03 | 20.23 | 16.40 |
| 6 overlapping monthly tranches | 16.71 | 13.40 | 19.96 | 16.42 |
| buy top 1/3, sell below top 1/2 | 16.77 | 13.30 | 20.17 | 15.04 |

The same holds for other holding counts:

| variant | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| top 1/5, sell below top 2/5 | 17.57 | 13.57 | 21.57 | 14.98 |
| top 1/10, sell below top 1/4 | 18.41 | 13.43 | 23.42 | 14.18 |
| top 1/5, 3 overlapping monthly tranches | 18.25 | 14.83 | 21.63 | 16.62 |
| top 1/10, 3 overlapping monthly tranches | 19.31 | 15.48 | 23.10 | 17.35 |

With 5 bp costs, turnover is cheap and signal freshness matters more. The dev_a losses come from the older, slower tranches.

**Rebalance-day timing luck (monthly, trading day d of the month):**

| holdings | day 0 | day 5 | day 10 | day 15 |
|---|---:|---:|---:|---:|
| top 1/3 | 17.58 / 15.93 early | — | 17.47 / 14.37 early | — |
| top 1/5 | 18.58 / 16.67 early | 19.12 / 14.89 early | 19.02 / 15.72 early | 18.99 / 15.28 early |

- The early window swings by up to about 2 points depending on the day, which is pure timing luck.
- This is the reason for the 4 intra-month tranches.

**Four staggered intra-month tranches (days 0/5/10/15):**

| configuration | dev | dev_a | dev_b | early |
|---|---:|---:|---:|---:|
| eq top 1/3 | 17.56 | 14.99 | 20.02 | 15.97 |
| rank top 1/3 | 18.70 | 15.85 | 21.46 | 16.84 |
| eq top 1/5 | 18.96 | 15.83 | 22.01 | 16.64 |
| rank top 1/4 | 19.28 | 16.20 | 22.27 | 17.28 |
| **rank top 1/5 (final)** | **19.62** | **16.43** | **22.73** | **17.69** |
| rank top 1/5, weights capped at 1.5× equal weight | 19.58 | 16.28 | 22.81 | 17.54 |
| rank top 1/7 | 19.84 | 16.71 | 22.89 | 18.80 |
| eq top 1/7 | 20.02 | 16.19 | 23.81 | 17.50 |
| eq top 1/10 | 19.79 | 16.47 | 23.04 | 19.85 |

**Why this point:**
- The surface is smooth and monotone from the top half to about 1/7–1/10, then turns down.
- I chose rank-weighted top fifth (about 8 effective names), which sits in the middle of the rising region, and deliberately did not take the 1/7–1/10 peak.
- Its neighbours (rank top 1/4 and top 1/7, the capped variant, and eq top 1/5) all score within about 0.7 points on dev and all beat the baseline in every window.
- Staggering is a variance reducer, not a tuned parameter. It changes the baseline by only −0.02 points on dev.

## Configurations evaluated: 43
The count includes the baseline replication. All are logged in `grid_log.jsonl`. The final strategy is config #37 in that log, re-run through the CLI with identical numbers. It passed the causality audit and uses no leverage.

`research.py` caches targets computed once on the full dev data, which is valid because every quantity is causal. It is research-only. `strategy.py` is uncached and audited.

## Risks
- **Concentration.** The book holds about 10 names and a top weight of up to about 18% at formation, spread over 4 tranches. Momentum crashes, such as a sharp rebound led by past losers, will hit harder than the top-third baseline. The worst relative years in round 1 were rebound years.
- **Selection bias.** The 43 configurations were all tried on the same history, and choosing concentration from them is exactly what the holdout will test. The pattern that concentration helps is consistent across all four windows and matches the literature, but its magnitude may shrink after 2000, when industry momentum was weaker.
- **Leaning on thin data.** Early-window numbers rest on fewer industries (6 start only in 1963–69) and only a few years of warm-up. Top-tenth results there vary a lot with the rebalance day, so no extreme configuration was chosen.
- **Rebalancing more often.** The book trades on 4 days per month, but each tranche is monthly and the total turnover matches a monthly book. The signal skips the most recent month, so stale-price effects should not matter.
