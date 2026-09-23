# r2:transformer_rule49: transformer cross-sectional ranker on 49 industries (negative result)

## Bottom line
A set-attention transformer, trained end-to-end to maximise monthly log growth, **does not add
robust value** over plain 12-1 momentum on the 49 industries. It wins dev_b (1975–99) by up to
+3.4 points but loses dev_a (1950–74) by 1.2 to 2.5 points. A linear model on the same features
shows the same era split, so what the models learn is era-specific, not a better ranker. The
honest final is therefore **the rule itself**. `strategy.py` is plain 12-1 momentum: the top third
of the valid i49 industries, equal weight, rebalanced on the first trading day of each month. It
runs through the same feature code (`r2t_core.py`) as the research. It adds nothing over the
team baseline. This directory's contribution is the evidence that the learned ranker should not
be used.

## Final results (harness CLI, `result_*.json`)

| window | final (= rule) | baseline 12-1 rule | buy & hold |
|---|---:|---:|---:|
| dev 1950–99 | 17.58% | 17.58% | 13.40% |
| dev_a 1950–74 | 15.08% | 15.08% | 9.42% |
| dev_b 1975–99 | 19.98% | 19.98% | 17.53% |
| early 1932–49 | 15.97% | 15.97% | 10.52% |

## Research (walk-forward, `research/wf.py`, results in `research/wf_*.json`)

**Features** (per industry, float64 cumulative sums, so they are batch-invariant; 13 in total):
* vol-normalised log returns over 1, 3, 6, 9 and 12 months;
* 12-1 momentum, both vol-normalised and raw;
* path smoothness: the 12-month return divided by the sum of |5-day returns|, which is the
  round-1 "ruler" finding;
* log 1-year vol, and the ratio of 3-month to 1-year vol;
* the cross-sectional rank of 12-1 momentum;
* market state: the market's 12-month z-return and the cross-sectional dispersion of 12-1.

Validity follows the rule: at least 250 valid days out of the last 252.

**Models.**
* **Transformer.** An embedding (d=32), then 2 set-attention blocks (4 heads, FF 64, dropout
  0.1) over the valid industries only, using a key-padding mask. There are no identity
  embeddings, so the model is permutation-equivariant. A score head adds a linear skip to the
  attention output, and a masked softmax gives long-only, fully-invested weights. The model is
  initialised to equal weight.
* **Linear control.** The score is w·x on the same features, followed by the same softmax.

**Training.**
* **Loss.** The loss is −mean monthly log growth, net of 5 bp × turnover measured against
  drifted weights. The labels use the harness 1-day lag: a decision at t is held from t+2 to
  t′+1. Optimiser: full-batch AdamW (lr 2e-3, wd 0.1).
* **Ensemble.** Four members, one per contiguous time fold. Each member early-stops on its own
  held-out fold, with a 1-month purge, and the ensemble averages their weights. This follows
  the round-1 recipe.
* **Walk-forward schedule.** The models are refit from scratch on an expanding window, on a
  fixed calendar grid: January of years divisible by 3, from 1932 to 1998. Seeds are derived
  from the grid year.
* **Fallback.** When a grid date has fewer than 120 months of history, the strategy uses the
  rule. As a result, early 1932–37 is pure rule.

All parameters were fixed a priori and none were tuned.

| # | variant | dev | dev_a | dev_b | early |
|---|---|---:|---:|---:|---:|
| 0 | rule 12-1, top third (reproduction of the baseline) | 17.58% | 15.08% | 19.98% | 15.97% |
| 1 | linear softmax | 17.48% | 13.49% | 21.39% | 15.14% |
| 2 | linear, 50/50 blend with rule | 17.57% | 14.32% | 20.73% | 15.57% |
| 3 | linear score → top third, equal weight | 17.17% | 14.11% | 20.16% | 15.44% |
| 4 | transformer softmax | 17.98% | 12.59% | **23.41%** | 16.09% |
| 5 | transformer, 50/50 blend with rule | 17.89% | 13.92% | 21.81% | 16.07% |
| 6 | transformer score → top third, equal weight | 17.44% | 13.86% | 20.96% | 14.81% |

**Configurations evaluated: 7.** These are the 6 learned variants plus the rule reproduction,
each scored on 4 windows. On top of that there are the 4 final harness runs of the chosen
strategy, which is identical to row 0. No other settings were run.

## Reading
* **The learned signal is era-dependent.** Every learned variant beats the rule in 1975–99 and
  loses to it in 1950–74, including the linear one. The transformer amplifies both sides.
  Because the linear model shares the pattern, the cause is most likely a regime-dependent
  feature tilt, such as toward vol or short-horizon returns, rather than the architecture.
* **Early is uninformative for the models.** Early 1932–49 is roughly a tie with the rule
  (+0.1 points for rows 4 and 5). The models are only active from 1938 and train on about 10
  years of data.
* **Using the learned ranking as a stock picker hurts.** Picking the top third by learned score
  (rows 3 and 6) is worse than the rule in 3 of 4 windows. So the learned ordering is not a
  better ranking than 12-1. Where the softmax gains anything, it comes from concentrating on
  a few names in dev_b.
* **The blend does not clear the bar.** The 50/50 blend (row 5) scores +0.3 dev, which is within
  noise after 7 tries. It also scores −1.2 in dev_a. That fails the brief's "beat the baseline
  on most windows robustly" standard, so it was not chosen.
* **Cost.** The transformer walk-forward takes more than 20 minutes on one core for the full grid.

## Risks
* The final is the baseline. Its holdout risk is the risk of 12-1 industry momentum itself:
  momentum crashes in sharp rebounds (1975- and 2009-style years), and drawdowns are
  market-like.
* If the orchestrator still wants a learned component, variant 5 is the least bad. Expect it
  to land anywhere between −1.5 and +2 points of the rule, depending on the regime.

## Files
* `strategy.py`: the final strategy (the rule).
* `r2t_core.py`: features, labels, SetRanker and LinearRanker, the trainer, and the ensemble.
* `research/wf.py`: the walk-forward and the replay scoring.
* `research/wf_{lin,tf}.{json,npz}`: the scores, and monthly weights for 1932–99.
