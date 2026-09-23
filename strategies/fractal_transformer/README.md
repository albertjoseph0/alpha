# hybrid:fractal_transformer_kelly: fractal-pretrained transformer volatility forecaster with a Kelly-capped market exposure

## Hypothesis
* Direction is close to a martingale. Volatility, however, is forecastable: it has long memory, a
  cascade that runs from long horizons to short ones, and a leverage effect
  (`dynamics_of_financial_markets.txt` pp. 3–5, 12–14; `mandelbrot_origins_of_econophysics.txt`
  pp. 5–6; book heresy 9, p. 275ff).
* Real data are scarce (about 19.6k days up to 1999). Wolfram's lore is that simulated data and
  transfer learning help (`what_is_chatgpt_doing_wolfram.txt` pp. 48–49). Bouchaud (2026, p. 7)
  proposes realistic synthetic series for "benchmarking of strategies". So I pretrain a small
  transformer on synthetic multifractal markets, then fine-tune it walk-forward on the real
  history.
* To turn the forecast into CAGR, I use the growth-optimal (Kelly) fraction f = μ/σ². It is capped
  at 1 because the harness allows no leverage. Exposure only drops when forecast volatility is high
  enough that the Kelly fraction falls below 1.

## Method
1. **Synthetic corpus** (`ft_sim.py`): 384 paths × 4,000 days, fixed seed, and generic literature
   parameters drawn from broad priors (domain randomisation). No real data is used in this step.
   * 45% **MRW with leverage** (Borland et al. eqs. 10–12, pp. 8–10). Causal 1/√lag log-vol kernel
     with λ² ∈ [0.015, 0.06] (literature 0.03) and T ∈ [1, 10] years. A negative log-vol response to
     past standardised returns breaks the time symmetry (§5.4, p. 12). Student-t residuals.
   * 35% **multi-timescale ARCH / statistical feedback** (eqs. 14–15, pp. 13–14). Power-law K(k)
     over horizons of 1 to 512 days, G(r) = g₁r + r² with g₁ < 0.
   * 20% **MMAR**: Brownian motion in multifractal trading time, from a randomised 60/40 binomial
     cascade (book pp. 240–245).
   * Augmentation: stale-price smoothing (AC1 of 0 to 0.3, as in the dev data), random vol level
     and random drift.
   * The mixture matches the real stylized facts (`research/check_stylized.py`):

     | | daily kurtosis | monthly kurtosis | ACF of \|r\| at lag 1 / 50 / 150 | leverage corr | Hill α |
     |---|---:|---:|---:|---:|---:|
     | synthetic mixture | 13 | 7.4 | 0.29 / 0.08 / 0.05 | −0.06 | 3.5 |
     | real Mkt 1950–99 | 36 | 7.2 | 0.21 / 0.08 / 0.06 | −0.09 | 3.5 |
2. **Inputs** (`ft_model.py`): 64 daily tokens. Each token is normalised return, log amplitude,
   log EWMA variance at half-lives 2/10/50/250/1000 days, and 21- and 126-day normalised returns
   (the r̃ of eq. 15). Everything is divided by the 50-day EWMA variance at the decision date, so the
   model is **scale-free** and synthetic worlds of any vol level transfer. All features are causal
   IIR filters, and inference runs in float64, so predict is batch-invariant and passes the audit.
3. **Model**: a 2-layer, 4-head, d=32 transformer encoder (about 20k parameters) read out at the
   last ("next-token") position.
   * Heads: log of the variance over days t+2…t+1+h, for h = 5, 21 and 63. The targets start at
     t+2 to respect the execution lag.
   * Loss: QLIKE, exp(y−ŷ)+ŷ, which gives unbiased variance forecasts.
4. **Training**
   * Pretraining: 1,500 AdamW steps at batch 256, run inside the first `fit()` and cached in memory.
     It takes about 3.5 minutes.
   * Fine-tuning: on Mkt plus the 12 industries as 13 univariate series, using all data up to the
     refit date. The first fit runs 300 steps; later refits warm-start with 120 steps at
     lr 3e-4. `refit_every = 504`.
5. **Trading**: w_Mkt = min(1, μ̂ / σ̂²₂₁), where σ̂²₂₁ is the annualised 21-day forecast variance.
   μ̂ is the arithmetic mean excess return of Mkt over T-bills, using all data up to the refit date
   (full Kelly, no tuned constant). The rest sits in cash.

**Parameters.** None was tuned on dev CAGR. Generator priors come from the literature. Model size
and step counts were set by the CPU budget. The Kelly fraction is full Kelly (theory), and the
horizon (21 days) was fixed a priori.

## Results (harness CLI)
| window | strategy | buy & hold |
|---|---:|---:|
| dev 1950–99 | **+13.39%** | +13.40% |
| dev_a 1950–74 | +9.34% | +9.42% |
| dev_b 1975–99 | +17.36% | +17.53% |

The dev run takes **492 s** single-threaded, including pretraining (dev_a and dev_b take about
320 s each). The causality audit passed on all windows.

## Pretraining ablation (`research/ablation.py`, walk-forward on dev, same schedule as the harness)
Forecast quality is out-of-sample QLIKE of the Mkt variance forecast from 1950 to 1999 (lower is
better). The CAGRs come from the harness-identical simulator in `research/simlib.py`: its dev figure
for the final model is 13.39%, the same as the CLI. dev_a and dev_b are sub-periods of the dev pass.

| variant | QLIKE 5d | QLIKE 21d | QLIKE 63d | dev | dev_a | dev_b |
|---|---:|---:|---:|---:|---:|---:|
| EWMA hl=10 (baseline) | 0.462 | 0.317 | 0.364 | 13.31% | 9.44% | 17.31% |
| EWMA hl=50 (baseline) | 0.490 | 0.326 | 0.303 | 13.30% | 9.42% | 17.31% |
| scratch + fine-tune (no pretraining, same steps on real data) | 0.397 | 0.253 | 0.270 | 13.31% | 9.37% | 17.39% |
| scratch, long (1,800 first steps = same total compute) | 0.404 | 0.270 | 0.281 | 13.28% | 9.26% | 17.43% |
| pretrained, zero-shot (never sees real data) | 0.402 | 0.253 | **0.242** | 13.22% | 9.36% | 17.22% |
| **pretrained + fine-tune (final)** | **0.390** | **0.250** | 0.265 | **13.39%** | 9.34% | **17.58%** |

What the ablation shows:
* **Pretraining helps the forecasts.** The final model has the best 5-day and 21-day QLIKE.
  Training from scratch for the same total compute overfits the scarce real data (21-day QLIKE
  0.270 against 0.250).
* **The synthetic-only model is striking.** It never sees a real return, yet it forecasts real
  1950–99 volatility far better than EWMA (0.253 against 0.317) and best of all at 63 days.
  Wolfram's "simulated data" lore holds when the simulator is Mandelbrot/Bouchaud's.
* **The CAGR differences are noise.** They stay within ±0.1–0.2%/yr, far below the standard error
  of about 2%/yr. Under the no-leverage cap, full Kelly holds about 99.8% exposure on dev, so the
  forecast only matters in the few high-vol episodes. On CAGR, pretraining is +0.08% on dev
  against scratch, −0.03% on dev_a and +0.19% on dev_b.

## What else I tried (local simulator, not harness runs)
* EWMA vol-timing, min(1, c/σ²) with c = 0.02–0.06: dev 11.9–13.3%. It never beats buy & hold on
  dev. It only helped slightly on dev_a.
* Inverse-vol and inverse-variance industry weights: dev 12.8–13.3%, below equal weight (13.56%).
  Low-vol industries lagged on dev, so I dropped the cross-sectional use.
* Half Kelly (0.5·μ̂/σ̂²): 13.16% on dev for the final model, lower for every variant. Full Kelly was
  the a-priori choice and was kept.

**Evaluation count:** 3 harness CLI runs (dev, dev_a, dev_b of the final strategy), 4 walk-forward
transformer passes on dev (the ablation), and about 45 cheap local-simulator evaluations of simple
rules and sensitivities. No holdout run.

## Known risks
* On dev this is essentially buy & hold with a crash brake. Its out-of-sample edge depends on
  high-vol regimes. Forecast vol has to exceed √μ̂, about 28% a year, before exposure drops. Fast
  V-shaped crashes that rebound while vol is still high would cost CAGR, and slow high-vol bear
  markets would gain.
* μ̂ is an expanding historical mean. If the equity premium is lower after 2000, the true Kelly
  fraction is lower and the rule is too aggressive (at worst about buy & hold).
* The fine-tuning data are dominated by the dev period's stale-price autocorrelation. The
  augmentation covers AC1 from 0 to 0.3, but post-2000 negative autocorrelation is out of the
  training distribution. It matters little for variance forecasts.
* The runtime of about 8–9 minutes is well inside the budget. The harness itself looks fine to me:
  the simulator reproduced the CLI CAGR to 4 decimals.

## Reproduce
```
.venv/bin/python -m harness strategies/fractal_transformer/strategy.py [--window dev_a|dev_b]
cd strategies/fractal_transformer/research && python ablation.py ewma pretrain_ft pretrain_zeroshot scratch_ft scratch_ft_long && python kelly_sens.py
```
No packages were installed.
