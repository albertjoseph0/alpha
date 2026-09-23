# transformer:alloc_axial_ens4_noweeksign: end-to-end transformer allocator

## Result (harness, final strategy)

| window | CAGR | EW 13 assets, weekly (same schedule) | buy & hold Mkt |
|---|---:|---:|---:|
| **dev** 1950–1999 | **+14.74%** | +13.47% | +13.40% |
| dev_a 1950–1974 | +10.40% | +9.82% | – |
| dev_b 1975–1999 (standalone run, own fit dates) | +18.94% | +17.24% | – |

* Dev runtime: **607 s** (10 min) single-threaded, with 17 refits × 4 members. The causality audit passed (102 dates).
* The strategy is reproducible. The research walk-forward script and the harness give the identical dev CAGR (0.1474).
* Number of dev evaluations: **5 walk-forward variants**. Three are learned (transformer, transformer without last-week sign, linear) and two are non-learned baselines (EW, inverse-vol). There were also 5 diagnostic re-scorings of saved weights (delays and smoothing, no retraining) and the 3 final harness runs (dev, dev_a, dev_b). No hyper-parameter was tuned: all were fixed a priori (below) and never changed.

## Hypothesis (with sources)

* **What to learn.** Direction is close to a martingale, but volatility structure, the leverage effect and medium-horizon cross-sectional effects are partly forecastable (REVIEW §5; Mandelbrot heresy 9, `misbehavior_of_markets_mandelbrot.txt` pp. 272–277; Bouchaud p. 5). A net should only be asked to capture learnable regularity, not irreducible randomness (Wolfram pp. 52–55).
* **Objective = the score.** Train end-to-end on the harness objective itself: the mean log growth of the portfolio, which is in-sample CAGR (Wolfram p. 45: end-to-end usually beats hand-crafted pipelines). The harness frictions are built into the loss: a 1-day execution lag, 5 bp × turnover against drifted weights, and Σ|w| ≤ 1.
* **Inductive bias.** Borland et al. (`dynamics_of_financial_markets.txt` pp. 13–14, eqs. 14–15) model volatility as a kernel over past returns at many horizons k, σ² = σ₀² + Σ_k K(k) G(r̃_k), with G(r) = g₁r + g₂r². Temporal attention over dyadic multi-horizon tokens (normalised returns r̃_k and log-vols) is the learned version of this kernel. Cross-asset attention lets each industry be judged relative to the others and to cash.
* **Transformer anatomy.** Wolfram pp. 63–70: token embedding + positional embedding, then attention blocks, then decoding a summary vector with a softmax. Here the softmax runs over 13 assets + cash, not over a vocabulary.
* **Overfitting.** Wolfram p. 44: many weight settings fit equally well but extrapolate differently. Wolfram pp. 73, 79: size the net to the data, and more training can degrade it. So the model is tiny (4.7k parameters for about 3.7k weekly samples by 1999), and the ensemble averages four members stopped on different eras.

## Method

* **Tokens.** For each asset, 6 time blocks back from the decision day, in trading days: 1–5, 6–21, 22–63, 64–126, 127–252, 253–504. Each token has 3 features:
  * the block's log-return divided by (252-day RMS vol × √length), soft-clipped at ±4. This is fat-tail safe (Mandelbrot ch. VIII).
  * the block's log realised vol (annualised, relative to 16%), soft-clipped.
  * the 252-day log vol level.
  * **Final choice:** the signed return of the 1–5 day block is zeroed. Its volatility is kept.
  * All features come from float64 cumulative sums, so they are batch-invariant.
* **Model.** Factorised ("axial") transformer with d = 16, 2 heads, FF 32, dropout 0.1, and 1 temporal plus 1 cross-asset block.
  * Temporal attention runs within each asset over [CLS, 6 time tokens].
  * Cross-asset attention runs over the 13 CLS tokens plus a cash token.
  * Embeddings: time-block positional embedding and a market-vs-industry type embedding. There are **no per-asset identity embeddings**, so the model is permutation-equivariant over industries and cannot memorise "industry X won in-sample". It can only learn rules on features.
  * The shared linear head reads the CLS tokens and a cash head reads the cash token, followed by a softmax over the 14 scores. Weights are long-only with Σw = 1, so Σ|w| ≤ 1 holds by construction.
  * Initialisation is equal weight with about 0.6% cash (zero-initialised heads, cash bias −2.5).
* **Schedule.** Decisions are made on the first trading day of each ISO week. Other days return NaN (hold / drift, as in the engine). The label for decision t is the gross growth over rows t+2 … t′+1, where t′ is the next decision, which is exactly the harness lag.
* **Loss.** −mean over weeks of [log(Σ w·G) + log(1 − 5bp·turnover vs drifted weights)]. It is computed on shuffled contiguous chunks of 26 weeks, 16 chunks per step, with AdamW (lr 2e-3, wd 0.1), gradient clipping at 1, and at most 30 epochs.
* **Ensemble / early stopping.** The weekly samples available at the fit date (expanding window from 1928) are split into K = 4 contiguous time folds. Member k early-stops (patience 6) on the log growth of fold k and trains on the other folds, with a 2-week purge. Weights are averaged over members and computed in float64 at predict time.
* **Walk-forward.** `refit_every = 756` trading days (3 years). Each fit trains from scratch with seeds derived from the fit date, so it is deterministic.

## What was tried (all on dev, in order)

| # | variant | dev | 1950–74 | 1975–99 | notes |
|---|---|---:|---:|---:|---|
| 1 | EW 13 assets, weekly (baseline) | 13.47% | 9.82% | 17.24% | |
| 2 | inverse-vol (252d), weekly (baseline) | 13.27% | 9.59% | 17.08% | |
| 3 | transformer, a-priori config, with last-week sign | **15.82%** | 11.44% | 20.37% | weekly turnover 0.50, avg max weight 0.36, HHI 0.24 |
| 4 | linear policy, same tokens / loss / ensemble (Borland-kernel baseline) | 14.11% | 10.32% | 18.04% | stays near EW (turnover 0.08, HHI 0.08) |
| 5 | transformer, no last-week sign (**final**) | 14.74% | 10.40% | 19.25% | turnover 0.31, max weight 0.25, HHI 0.16 |

The sub-period columns of rows 1–5 come from the single dev run's equity curve. The standalone dev_b harness run of the final variant, with different fit dates, gives 18.94%.

**Diagnostics on variant 3's saved weights** (no retraining). The same weights were applied with an extra delay:

| extra delay | dev CAGR |
|---|---:|
| +1 week | 15.16% |
| +4 weeks | 12.50% |
| +13 weeks | 12.99% |

Smoothing the weights with a 4-week average gave 15.68%.

**What the transformer learned.**
* It is almost never in cash: average cash is 0.6% and it is never below 94% invested. So there is essentially no market timing: under the no-leverage cap, the log-growth optimum is to stay invested (the Kelly fraction for equities is far above 1).
* All the gain comes from **cross-sectional industry selection with a horizon of a few weeks**. The edge survives one extra week of delay, so it is not the daily stale-price artifact the harness lag removes. It is gone after one month.
* Per-feature rank correlations of the weights are about 0, so the rule is non-linear or conditional (attention), which a linear read-out does not capture (row 4 vs row 3).

**Why the final is variant 5 and not variant 3.** About a third of variant 3's edge came from the signed return of the most recent week. That is exactly where the dev-era artifacts sit: stale-price autocorrelation (lag-2 is −0.08 to −0.10 in the 1940s–50s) and weekly lead-lag between industries. REVIEW §5 shows short-horizon persistence changes sign after 2000. I chose the version that does not read last week's direction. It gives up 1.1 points of dev CAGR but still beats EW, buy & hold and the linear policy in both halves.

Note: `research/runs.jsonl` holds the raw log. Its `a` / `b` fields were computed with a buggy date slice (since fixed in `wf.py`). The corrected values are the ones in the table above.

## Parameters (all fixed a priori, none tuned)

d = 16, heads = 2, layers = 1 (temporal) + 1 (cross-asset), FF = 32, dropout = 0.1, AdamW lr = 2e-3, wd = 0.1, epochs ≤ 30, patience = 6, chunk = 26 weeks, 16 chunks per batch, 4 fold-members, purge = 2 weeks, refit every 756 days, weekly rebalance, time blocks as above, last-week sign off.

## Known risks (why it might fail out of sample)

* **Horizon of the edge.** The edge is a few-week cross-sectional industry effect. Short-horizon industry momentum and lead-lag effects were documented in exactly this period and have reportedly weakened since. The holdout could land anywhere between EW and EW minus 1–2%. The costs from about 31% weekly turnover (≈0.8%/yr) are paid whether or not the signal works.
* **No crash protection.** The model stays about 100% invested, so it takes the full 2000–02 and 2008 drawdowns.
* **Noise.** The +1.3 point dev edge over EW is below the ~2%/yr standard error of a 50-year CAGR, although it appears in both halves and the design was not tuned.
* **Concentration.** The average maximum weight is 25%, which means sector-concentration risk in a bubble or bust (e.g. BusEq in 2000).
* **Ensemble variance.** Early stopping on noisy validation folds makes individual members nearly random in stopping epoch. Four members average this out only partly.

## Files

* `strategy.py`: final Strategy (`TransformerAllocator`).
* `ta_core.py`: features, weekly schedule, samples, model, loss, training, ensemble.
* `research/wf.py`: fast walk-forward and baselines. `research/runs.jsonl` holds the run log, `research/w_*.pkl` the saved weights, and `research/log_*.txt` the logs.
* `result_dev.json`, `result_dev_a.json`, `result_dev_b.json`: harness outputs.

No packages were installed.
