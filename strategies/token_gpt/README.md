# transformer:gpt_token_kelly: the market as a language

## Hypothesis
Wolfram describes an LLM as a model that "just adds one token at a time". It outputs a
probability distribution over the next token (what_is_chatgpt_doing_wolfram.txt pp. 10–16).
That distribution comes from a parametric model because the n-gram table explodes
(pp. 17–23). The model is built as token + position embeddings, then causal attention
blocks, then a softmax decoder (pp. 63–71). If returns are turned into tokens, a tiny GPT
gives a full **predictive distribution** of the next return "word".

The finance documents say what that distribution can and cannot know:
* Signs are close to a martingale, but magnitudes are dependent ("dependence without
  correlation"; misbehavior_of_markets_mandelbrot.txt pp. 275–276, heresy 9).
* Volatility clusters, and there is a leverage effect (dynamics_of_financial_markets.txt
  pp. 3–5).

So the decoder does not bet on the predicted sign. It converts the distribution into:
1. **How much risk to take**: a Kelly fraction for the market, `f = E[R]/Var[R]`, clipped
   to [0, 1]. The distribution's variance is where the forecastable information lies, and
   `f` is almost always 1. It drops only when the predicted distribution is very wide or
   shifted down.
2. **Where to put it**: a softmax with temperature over the 12 industries' predicted mean
   (vol-normalised). This is Wolfram's temperature (p. 12). At T→0 the portfolio goes
   all-in on the top industry, and at T→∞ it becomes equal weight. A per-asset model that
   learns time-series momentum ranks industries by it. Mandelbrot p. 126 (Jegadeesh–Titman)
   discusses momentum, and my exploratory check found industry momentum in all three eras
   (1927–49, 1950–74, 1975–99), with IC about +0.06 to +0.08.

## Method (gpt_core.py, strategy.py)
* **Tokens.** A "word" is one asset's 5-day excess log return (net of T-bills), divided by
  the trailing EWMA volatility known before the word starts. The EWMA has a 30-day
  half-life, truncated at 250 days so that the calculation is batch-invariant. Each word is
  binned into K = 16 equal-frequency bins. The bin edges are fitted at the first fit and
  then frozen, so the vocabulary never changes.
* **Sentences.** A sentence is the last L = 64 non-overlapping words (about 15 months),
  aligned so the last word ends on the decision day. Every day gives a differently phased
  tokenisation of the same history, which is free data augmentation (Wolfram pp. 48–49).
  Two input channels are summed: the asset's own token and the market's token at the same
  position, plus a learned position embedding. There is no asset-identity embedding, so the
  same "grammar" applies to all 13 assets (heresy 6) and the model cannot memorise which
  industry did well.
* **Next *tradable* token.** At each position the target is the binned return over days
  t+2 … t+6, not t+1 … t+5. This matches the harness execution lag, so the model cannot
  learn the stale-price day-1 autocorrelation (REVIEW.md §5). All positions are trained
  GPT-style with causal masking.
* **Model.** A tiny GPT: d_model 32, 2 pre-LayerNorm attention blocks with 2 heads each,
  MLP width 64, dropout 0.1, about 21k weights. It is trained with AdamW (lr 1e-3, weight
  decay 0.1, batch 64 random (asset, day) sentences). It uses 3 seeds and averages their
  softmax outputs.
* **Walk-forward.** It refits every 504 decision days. The first fit runs 400 steps from
  scratch. Each later refit warm-starts from the previous weights and runs 150 steps
  (lr 5e-4) on all history up to the refit date. Seeds come from the fit date, so runs are
  deterministic.
* **Decoding.** The model outputs p(k). A per-bin table of the mean and mean-square of the
  target z (from the training data) gives E[z] and Var[z]. These are averaged over the last
  5 daily tokenisations ("phases") to reduce turnover. Then:
  * market Kelly: `f = clip(E[z]·σ√5 / (Var[z]·σ²·5), 0, 1)`;
  * industry weights: `f · softmax(standardised E[z_industry] / T)` with T = 1.
  * `Mkt` weight is 0, and the rest is held in cash.
* **Causality.** Inference uses float64 copies of the models, and every feature is a
  fixed-window function of the past. The harness audit passes (102 audited dates on dev).

## Parameters
H = 5, L = 64, K = 16, d = 32, 2 layers, 2 heads, dropout 0.1, 3 seeds, 400 / 150 steps,
refit every 504 days, industry temperature T = 1, Kelly temperature 1 (full Kelly, capped
at 1).

None of these was tuned on 1950–99. The step budget came from a learning curve on
**pre-dev** data only (train on data through 1944, validate on 1945–49; see
`research/diag_curve.py`).

## Results (harness CLI)
| window | strategy | buy & hold Mkt | EW industries |
|---|---:|---:|---:|
| dev 1950–99 | **+14.11%** | +13.40% | +13.54% |
| dev_a 1950–74 | +13.11% | +9.42% | +9.91% |
| dev_b 1975–99 | +14.50% | +17.53% | +17.13% |

Runtime of the final dev run: 915 s (about 15 min, on a shared 4-core machine;
user time about 10 min). dev_a and dev_b each took about 7 min.

**Number of dev evaluations: 1 dev run, plus 1 each for dev_a and dev_b, all on the
final configuration.** No variant was selected on dev CAGR. Before the dev run I did some
exploratory statistics on dev data (`research/explore.py`, `research/explore_xs.py`):
conditional means by vol, vol-ratio and momentum quintiles, and industry signal ICs.
These shaped the design: de-risk only selectively, and rank industries by the model's
mean.

## What was tried and learned
* **Pre-dev learning curve** (d = 32, 2 layers, L = 64). The validation cross-entropy of
  the next tradable token barely beats the unconditional token frequencies: the best was
  2.7746 at about 400 steps against a baseline of 2.7728 (ln 16 = 2.7726). After that the
  model overfits (2.82 by 2000 steps). This is Wolfram's warning that more training
  "degrades performance" (p. 79), and the martingale property in action. The next-token
  distribution is almost unpredictable, so the decoder must be conservative. That is why
  the budget is short, the model warm-starts, there are 3 seeds, and the output is averaged
  over 5 phases.
* **Exploration of the dev period.** Unconditional Kelly fractions for the market are
  about 2–10, i.e. far above the no-leverage cap, in every vol quintile of 1950–99. Market
  timing therefore has little room, so the Kelly overlay mostly stays at f = 1. Market-level
  momentum and vol effects flip sign between 1950–74 and 1975–99. Industry momentum was
  the only effect that was consistent in all three eras.

## Known risks (why it may fail out of sample)
* **The edge is not stable across halves.** It is +3.7%/yr over buy & hold in dev_a and
  −3.0%/yr in dev_b. The whole-period gain (+0.7%/yr) is well inside the ~2%/yr standard
  error of CAGR. Treat it as "about market-like with a momentum tilt", not as proven alpha.
* The model's own signal is weak (the cross-entropy gain is about 0.002 nats). The industry
  tilt is effectively a learned, noisy time-series-momentum ranking. Industry momentum has
  suffered sharp crashes after bear markets (e.g. rebounds), and the holdout contains two.
* The Kelly overlay acts on a noisy predicted mean. It can de-risk at the wrong moments,
  which risks missing the few best days (heresy 3). In 1975–99, high-vol periods had
  *high* subsequent returns.
* The bin edges come from the pre-1950 vocabulary. The decoding table and the model are
  refitted, but a regime with very different vol dynamics (post-2000 autocorrelation turned
  negative) is out of distribution.
* Runtime is about 15 min on a loaded machine. The holdout (26 years) should be similar or
  shorter.

## Files
`strategy.py` (final strategy), `gpt_core.py` (tokenizer, TinyGPT, trainer, decoder),
`research/diag_curve.py` (pre-dev learning curve), `research/explore*.py` (exploration),
`result_dev.json`, `result_dev_a.json`, `result_dev_b.json`.
