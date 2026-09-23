# fractal:tails_chiseled_frontier (Noah effect: tails and crash avoidance)

## Result (harness, 5 bp costs, 1-day lag, no leverage)
| window | strategy | buy & hold Mkt | EW industries |
|---|---:|---:|---:|
| dev 1950–99 | **+15.64%** | +13.40% | +13.54% |
| dev_a 1950–74 | +11.97% | +9.42% | +9.91% |
| dev_b 1975–99 | +19.24% | +17.53% | +17.13% |

- Full dev run: 36 s single-threaded, and the causality audit passes.
- Dev evaluations: 21 in total. That is 20 strategy variants scored with the exact harness engine in `research/bt.py` (logged in `research/evals.log`; 5 of those were a buggy batch that sat in cash) plus 1 harness dev run of the final strategy. Descriptive analyses (`explore1–3.py`) were also run on 1927–99 data.
- Vol 12.8% (market 12.6%). Max drawdown −46% (market −48%).

## Hypothesis (with sources)
- Losses come from a few crashes, and those crashes hit many assets together. Tails are power-law, α≈1.7 for cotton (book ch. VIII, p. 163 of the PDF text). For liquid indices the tail exponent μ is 3–5, so the tails are not Lévy-stable (Borland et al. p. 4; Bouchaud 2026 p. 4). My Hill estimates for dev match this: about 3.6 for the vol-filtered left tail, heavier than the right tail at about 4.7.
- Bouchaud's "tail chiseling" builds portfolios that minimise the chance of too many assets crashing at once. It traces a *generalized efficiency frontier* that maximises return for a given level of crash protection (book "In the Lab", p. 288). Expected shortfall is the "overhang" beyond VaR (p. 301).
- You cannot forecast prices (heresy 9, p. 275–276), and sample means are unreliable under fat tails. So the return axis uses **ranks** of the one return regularity cited in the book, 6–12-month momentum (Jegadeesh–Titman, book pp. 126–128).

## Method
On the first trading day of each month, over the 12 industries, solve one linear program (Rockafellar–Uryasev):

- **Objective:** maximise Σ wᵢ·rankᵢ(12-1 month momentum).
- **Tail budget:** CVaR₉₅ of the portfolio's daily returns over the trailing 5 years must not exceed CVaR₉₅ of the market over the same window. Because this uses the joint history, it prices co-crashes between industries.
- **Constraints:** Σw = 1 and 0 ≤ w ≤ 0.25.
- **Between rebalances:** rows are NaN (hold).

Code: `tails.py` (Hill, CVaR, min-CVaR and frontier LPs) and `strategy.py`.

## Parameters
There are four, all fixed a priori and not tuned: 5-year tail window, CVaR level 95%, weight cap 0.25, and 12-1 momentum. The tail budget is "no worse than the market", so it has no free level.

## What I tried (dev / dev_a / dev_b CAGR)
**1. Descriptive checks.**
- *Do tail states predict returns?* In 1975–99, high vol, shock index, co-crash, downside-share and drawdown states were followed by the **highest** forward returns (+20–26%/yr in the top quintile). In 1950–74 and 1927–49 the results were mixed. Best days happen at higher vol percentiles (median 0.83) than worst days (0.74), which is heresy 3 (p. 262) in the data.
- *Do tail features rank industries?* Industry-level tail features (lower-tail dependence, Hill α, ES/vol, beta, downside beta, vol) have rank-IC ≈ 0 for next-month returns in all three periods. Only 12-1 momentum has a consistent rank-IC, with t≈3 in each period.

**2. Market-timing overlays on Mkt (tail de-risking).**

| variant | dev | dev_a | dev_b |
|---|---:|---:|---:|
| Kelly f = 6%/σ̂² with multi-scale vol | 13.30 | 9.42 | 17.31 |
| Kelly with fat-tailed filtered-historical residuals | 13.36 | 9.48 | 17.37 |
| Halve exposure when the Richter-style shock index > 1 | 13.18 | 9.46 | 17.03 |
| Halve exposure after co-crash days (≥9 of 12 industries below −2σ) | 13.48 | 9.16 | 17.96 |

None is reliably better than buy & hold (13.40). Tail-aware Kelly sizing is the same as vol-based Kelly: with daily rebalancing the higher moments barely change the optimal fraction. **So the tail measures add nothing beyond realized vol for timing**, and vol timing itself doesn't help in dev.

**3. Pure tail-chiseled allocation, all 12 industries, monthly.**

| variant | dev | dev_a | dev_b |
|---|---:|---:|---:|
| EW | 13.54 | 9.91 | 17.13 |
| Inverse vol | 13.35 | 9.68 | 16.97 |
| Tail parity, w ∝ ES^(−μ/(μ−1)) with μ=3 (Bouchaud et al. 1998 closed form) | 13.24 | 9.53 | 16.90 |
| Min-CVaR (67% Utils) | 11.07 | 7.30 | 14.67 |

Minimising tails lowers vol from 12.2% to 9.1% but also lowers CAGR, because the low-tail industries (Utils) had lower returns.

**4. Frontier and momentum variants.**

| variant | dev | dev_a | dev_b |
|---|---:|---:|---:|
| Momentum top-6 EW | 15.34 | 11.80 | 18.83 |
| Momentum top-6, min-CVaR weights | 12.55 | 10.11 | 14.74 |
| Momentum top-4 EW (= frontier with no tail cap) | 16.06 | 12.82 | 19.21 |
| **Frontier with CVaR ≤ market (final)** | 15.64 | 11.97 | 19.24 |
| Final + switch to EW in "quakes" (shock > 1) | 15.67 | 11.77 | 19.52 |

The quake overlay was dropped: it added nothing.

## Honest assessment
- **Where the CAGR comes from:** the excess over buy & hold comes from industry momentum, not from tails. The tail budget costs about 0.4%/yr in dev (all of it in dev_a) against uncapped momentum. In return it lowers vol by about 0.6% and caps concentration in high-crash-risk winners.
- **Why keep the cap:** I kept the capped frontier because it is the documented mechanism of this assignment and it limits holdout crash exposure. It is **not** justified by dev CAGR; the difference is inside the ~2%/yr noise band.
- **Tail timing:** tail and shock measures did not beat realized vol, and neither beat buy & hold for timing.

## Known risks (out of sample)
- **Momentum risk:** industry momentum can weaken or crash, especially in sharp V-shaped rebounds after crashes when past losers lead (heresy 3). The strategy has no crash de-risking. Its drawdowns are market-like (−46% in dev).
- **Tail budget is backward-looking:** the CVaR cap uses 5 years of history. Crashes that "come from nowhere" (Bouchaud 2026 p. 5) in industries that were calm before will not be anticipated.
- **Overlap with teammates:** others using momentum or trend will be correlated with this strategy.
- **Selection bias:** some selection bias remains from the 21 dev evaluations, even though the final strategy is not the best-scoring variant in dev.
