# fractal:mfvol_ttmom_kelly: industry momentum in multifractal trading time, Kelly-capped by MRW vol forecasts

## Hypothesis
* **Volatility is forecastable, while prices are not.** Heresy 9 (book p. 275–277, file `misbehavior_of_markets_mandelbrot.txt`): "you cannot forecast prices… but you can sidestep its worst punches." Log-volatility follows a cascade with log-decaying covariance, `C(τ) = λ² ln(T/(τ+1))`, with λ² ≈ 0.03 and T a few years (`dynamics_of_financial_markets.txt` pp. 6–10, eqs. 9–12, §5.2 p. 11). Bouchaud 2026 (pp. 5–7) calls long memory in amplitudes "the real empirical fact".
* **Trading time.** Mandelbrot models price as a process in *trading time* θ(t), where clock time runs fast in turbulent periods and slow in calm ones (book ch. XI pp. 235–250; heresy 5 pp. 266–268). I use the forecast variance as dθ. A trend is then measured as a z-score in trading time: Σr / √(Σ dθ).
* **Sizing.** Under the no-leverage cap, the growth-optimal (CAGR-maximising) fraction per position is min(1, μ/σ²). The vol forecast sets exposure only when turbulence makes Kelly < 1.

## Method (strategy.py, mfvol.py)
1. **Fit (annual refit, per industry).** Estimate λ² and T by regressing the empirical autocovariance of log|r| on −ln τ (lags 1–500). Solve the Toeplitz system for the MRW best linear predictor of mean log-vol over days t+2…t+22, using 1000 lags of log|r| and white log|ε| noise (π²/8). One level constant is calibrated. The fitted λ² is 0.023–0.028 on Mkt, close to the paper's 0.03. T saturates at the 5000-day clip.
2. **Score.** Σ log r over [t−251, t−21], divided by √(Σ forecast daily variance) over the same window.
3. **Positions.** On the first trading day of each month, hold the top 4 of the 12 industries at 1/4 each. Each position is multiplied by min(1, μ/σ̂²_ann), where μ is the long-run excess market return up to the fit date. The rest sits in T-bills. Other days are NaN rows (hold).

Parameters are few and set a priori: horizon 21 days, MRW length 1000, 12-1 momentum window (Jegadeesh–Titman style, book pp. 126–128), and top 4 (a third of the industries). λ² and T are fitted from data, not tuned.

## Results (harness)
| window | CAGR | buy & hold Mkt | EW industries |
|---|---:|---:|---:|
| dev 1950–99 | **+15.51%** | +13.40% | +13.54% |
| dev_a 1950–74 | +12.55% | +9.42% | +9.91% |
| dev_b 1975–99 | +18.43% | +17.53% | +17.13% |

The final dev run takes 178 s single-threaded, and the causality audit passed (102 dates).

## What was tried (research/, fast sim on the harness engine; dev CAGR, dev_a/dev_b)
**Forecast accuracy on Mkt.** I compared walk-forward 21-day realized-variance forecasts over 1950–99 (`research/forecast_eval.py`). Lower QLIKE is better.

| model | QLIKE | log-R² |
|---|---:|---:|
| EWMA 0.94 (baseline) | 0.314 | 0.409 |
| GARCH(1,1) | 0.284 | 0.354 |
| GJR | 0.339 | 0.416 |
| HAR-log (1/5/21/63/252 d) | 0.272 | 0.410 |
| **MRW** (1 free parameter) | 0.282 | 0.411 |
| Calvet–Fisher MSM k̄=6 (MLE) | 0.278 | 0.418 |
| multi-timescale ARCH eq. 15 with leverage (g1<0) | 0.315 | 0.330 |
| same, without leverage | 0.365 | 0.212 |

The multifractal models beat EWMA and GARCH, but only by a modest margin. MSM has the best R², but one fit takes about 2 min, too slow for annual refits. MRW is nearly as accurate and closed-form. The leverage term clearly helps the multi-timescale ARCH, but my direct-regression version of it is weak.

**Market-only exposure.** A Kelly cap w = min(1, μ/σ̂²) on Mkt is effectively buy & hold in dev: EWMA 13.26%, GARCH 13.28%, HAR 13.33%, MRW 13.41%, mt-ARCH 12.89%. Forecast vol exceeds about 25% on only 0.4–3% of dev days. Worse, the highest-vol quintile had the *highest* subsequent Sharpe in 1975–99 (`research/eda.py`). **Vol timing alone does not add CAGR under the no-leverage cap.**

**Industries** (monthly rebalancing):

| variant | dev | dev_a | dev_b |
|---|---:|---:|---:|
| EW | 13.54% | | |
| inverse-vol (MRW) | 13.18% | | |
| vol-proportional | 13.82% | | |
| clock-time 12-1 momentum, top 4 | 16.06% | 12.82% | 19.21% |
| trading-time drift Σr/Σσ̂² | 14.96% | | |
| **trading-time z-score, MRW clock** | 15.94% | 12.97% | 18.87% |
| trading-time z-score, EWMA clock | 14.86% | | |
| MRW z-score + Kelly cap (final) | 15.73% | | |
| top 3 | 15.94% | | |
| top 6 | 15.02% | | |
| 6-1 lookback | 13.71% | | |

**Honest attribution.**
* Most of the edge over EW is industry momentum, which is not a vol forecast.
* The multifractal part adds about +1.1% over an EWMA clock.
* The trading-time normalisation does *not* beat plain clock-time momentum (15.94% vs 16.06%, within noise).
* The Kelly cap costs about 0.2% in dev. I kept it deliberately as crash insurance.

**Number of dev evaluations.** There were 23 research simulations; the first 6 were invalid because of an evaluator bug with NaN hold rows, and were re-run. There were also 3 harness runs (dev, dev_a, dev_b). The MSM fits were forecast-accuracy runs only.

## Known risks
* **Momentum dependence.** Industry momentum was unusually strong in 1950–99, a period used in the published studies. It may be weaker after 2000. It is also prone to *momentum crashes*, i.e. sharp loser rebounds after bear markets. The Kelly cap only trims positions whose forecast vol is extreme.
* **Concentration.** Holding 4 of 12 industries is concentrated. Tracking error against the market is large.
* **Selection noise.** The dev margin over buy & hold (+2.1%/yr) is about one standard error of CAGR.
* **Slow forecasts.** The MRW forecast deliberately discounts single huge days (it is a log-scale predictor), so it reacts slowly to sudden crashes. The cap binds late.
* **Fixed μ.** μ is fixed at the long-run excess return. If the equity premium is lower after 2000, the cap would bind more often.

## Files
* `strategy.py`: the final strategy.
* `mfvol.py`: the forecasters (EWMA, GARCH/GJR, MRW, multi-timescale ARCH, MSM).
* `research/`: `eda.py`, `forecast_eval.py`, `bt.py` (evaluation counter), `wf.py`, `mkt_rules.py`, `xs_study.py`.

No packages were installed.
