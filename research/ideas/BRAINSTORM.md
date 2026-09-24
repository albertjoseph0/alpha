# 50 fractal × transformer strategy ideas (round 4 brainstorm)

Constraints every idea must fit: tradeable today, long-only, no leverage, daily data (ETF universe
2000–2026, French and proxy history back to 1926 or 1962). Each idea must be scorable by the existing
CAGR harness (1-day lag, per-ETF costs). "Novel" means the orchestrator does not know of a published
version and it was not tried in rounds 1–3. The critique pass checks that claim.

Already tried, so excluded as-is:
* Hurst gating of relative momentum (`hurst_regime`)
* MRW volatility forecast with trading-time momentum z-score and Kelly sizing (`multifractal_vol`)
* CVaR "tail chiseling" (`tail_risk`)
* Ruler-roughness rotation (`mf_spectrum`)
* Quantised-return GPT decoded into positions (`token_gpt`)
* End-to-end log-growth transformer allocator (`transformer_allocator`)
* Synthetic-multifractal-pretrained volatility transformer with Kelly sizing (`fractal_transformer`)
* Jump-winsorised momentum (`r2_fractal_momentum`)
* Set-attention ranker (`r2_transformer`)
* Volatility caps, per-asset trend gates, dual momentum (round 3 and the deep dive)

## A. Fractal representations fed to transformers
1. **Scale-as-sequence transformer.** The token axis is dyadic scale (1, 2, 4 … 256 days) instead of
   time. Each token is the asset's return and realised variance at that scale. Attention learns the
   cascade structure across scales. Target: next-month cross-sectional rank.
2. **Wavelet-leader tokens.** Tokens are wavelet leaders (the local maximum of wavelet coefficients)
   per scale and position, the standard multifractal estimator, used as a learned representation
   rather than just to estimate a spectrum.
3. **Log-spaced positional sampling.** The transformer sees 32 tokens at log-spaced lags (1 d … 2 y),
   so a short context covers the whole range of memory. It is a fractal "zoom" context.
4. **Trading-time tokens.** Each token is a bar of equal realised variance, not an equal number of
   days. Mandelbrot's trading time becomes the transformer's clock: calm periods compress and crises
   expand.
5. **Self-similar data augmentation.** Aggregate daily returns into k-day bars and rescale them by
   k^H, which multiplies the training data by about 8×. This exploits scale invariance to address
   the small-data problem that sank the round-1 and round-2 transformers.
6. **Hölder-exponent alphabet.** The token vocabulary is quantiles of the local Hölder (pointwise
   regularity) exponent per asset per week. It is a language of roughness rather than of returns.
7. **Hurst-conditioned attention span.** Each head's attention decay is set by that asset's local
   Hurst exponent: persistent regimes attend further back.

## B. Fractal quantities as the transformer's target
8. **Forecast next month's multifractal spectrum width** (intermittency) per ETF. Tilt momentum
   toward assets forecast to trend smoothly (a narrow spectrum is Joseph-like).
9. **Multi-task return rank plus next-month Hurst.** The Hurst forecast gates momentum per asset.
10. **Forecast the left-tail index per ETF.** Underweight momentum winners whose forecast tail is
    fattening.
11. **Masked scale modelling.** A BERT-style model on wavelet coefficients: mask the coarse-scale
    coefficients and reconstruct them from fine-scale ones. Its reconstruction at the latest
    position is a forecast of the coming trend component.

## C. Cross-asset fractality
12. **Fractal dimension of the correlation network.** Take the box-counting dimension of the
    cross-ETF correlation graph (or the transformer's attention graph). A collapsing dimension means
    everything moves together, a pre-crash signal used as the regime switch.
13. **Cross-asset multiplicative cascade.** Model volatility flowing through the tree
    world → region → sector → industry as an MMAR over assets rather than time. A tree-attention
    model predicts which branch the next cascade hits, and the strategy avoids it.
14. **Asset × scale lead–lag cross-attention.** A coarse-scale move in one asset (for example
    monthly copper or DBC) leads fine-scale moves in another.
15. **MF-DCCA diversifiers.** Pick defence-sleeve assets by multifractal detrended cross-correlation
    with SPY at long scales (63–252 d) instead of daily correlation or Sharpe.

## D. Generative and simulation approaches
16. **Scenario Kelly.** An autoregressive fractal transformer generates about 1000 one-month joint
    scenarios for all ETFs each month. Choose the long-only mix that maximises the median log growth
    over those scenarios.
17. **Generated-drawdown gate.** The same generator stress-tests the current momentum book and
    de-risks when the generated drawdown distribution fattens.
18. **Sim-to-real persistence detector.** Pretrain on MRW/MSM paths with planted trends of varying
    strength, so the transformer learns "is there tradable persistence here?". Apply it to real
    ETFs as a per-asset momentum gate. The target is new; `fractal_transformer` forecast volatility.
19. **Adversarial fractal null.** A classifier learns to tell real windows from IAAFT surrogates
    that preserve their multifractal spectrum and distribution. High confidence means there is
    structure beyond fractal noise, so trade momentum only there.
20. **Surrogate-significance filter.** Test each ETF's 12-1 momentum against 200 multifractal
    surrogates of itself. Hold only trends that are significant against the fractal null.

## E. Regime and time-scale
21. **MSM slowest-component regime.** The Calvet–Fisher MSM Bayesian filter gives the state
    probability of the slowest volatility component. Use it as the offense/defense switch instead of
    SPY trend.
22. **Zumbach cascade direction.** Detect whether volatility is flowing from coarse to fine scales
    (normal) or from fine to coarse (panic building) and switch to defense on the latter.
23. **Per-asset fractal lookback.** Each ETF's momentum lookback is set by its own estimated
    correlation time or Hurst exponent.
24. **LPPLS bubble exclusion via transformer.** Train a classifier on synthetic log-periodic
    power-law (discrete scale invariance) bubbles. Exclude assets flagged as late-stage bubbles from
    the offense sleeve.
25. **Discrete-scale-invariance crash hazard on SPY.** Turn the LPPLS critical-time estimate into an
    early defense trigger.
26. **Power-law ALiBi.** Replace ALiBi's linear attention bias with a power-law bias whose learned
    exponent plays the role of a Hurst exponent. The exponent is interpretable per asset.
27. **Learned fractional differencing.** The input is log price fractionally differenced with d
    learned end to end per asset, keeping long memory.
28. **fBm-kernel attention.** Attention weights equal the fractional Brownian motion covariance
    kernel with a learned H. This makes the model the optimal linear predictor under fBm, a
    transformer with physics in the kernel.

## F. Cross-sectional ranking on fractal features
29. **Fractal-only learning-to-rank.** A transformer ranks ETFs using only fractal features (H,
    spectrum width, tail index, current Hölder exponent, lacunarity), with no raw returns. This
    tests whether fractal state alone carries rank information.
30. **Lacunarity.** Measures how clustered an asset's big moves are compared with evenly spread.
    Prefer momentum whose gains came evenly rather than from one cluster.
31. **Pointwise Hölder at the latest point.** Buy positive-trend assets whose path is smooth right
    now (over the last 1–2 weeks). This is close to `mf_spectrum`, but local rather than one-year.
32. **Multiscale entropy-rate ranking.** Rank by sample-entropy slope across scales. Complexity
    that falls at coarse scales means a trend is emerging.
33. **Time-reversal asymmetry detector.** A transformer learns to tell forward windows from
    reversed ones. Forward-ness confidence per asset measures the irreversible, information-driven
    move and is used as a momentum-quality score.

## G. Fractal-aware training objectives
34. **Lévy-stable or Student-t likelihood with a learned tail index.** Train the return forecaster
    so that Noah days cannot dominate the loss.
35. **Scale-consistent multi-horizon heads.** Predict 1/5/21/63-day returns jointly, with a penalty
    forcing coarse forecasts to equal aggregated fine ones (a scaling-law consistency regulariser).
36. **Scale curriculum.** Train on monthly bars first, then weekly, then daily.
37. **Pooled-universe pretraining.** Pretrain on 1926–1999 French industries plus the 1962–99
    proxy, with each asset rescaled to a common trading time, then fine-tune on ETFs. This is about
    100× more sequences than the round-3 universe.

## H. Wolfram angle: compressibility and perplexity
38. **Lempel–Ziv compressibility filter.** Trade momentum only in assets whose recent sign sequence
    is compressible (computationally reducible).
39. **Perplexity regime switch.** A small next-token model is trained on quantised SPY returns.
    When its perplexity on the last month spikes (the market is "speaking an unfamiliar language"),
    switch to defense. `token_gpt` traded its predictions directly; this uses surprise as a regime.
40. **Per-asset perplexity ranking.** Hold trending assets whose recent behaviour is most
    predictable, i.e. has the lowest perplexity.
41. **Embedding-trajectory momentum.** Embed each ETF's recent windows. Hold assets whose embedding
    is moving toward the region historically followed by high forward returns.
42. **Fractal analog forecasting.** Search all history at every time scale, with windows rescaled
    by k^H, for the closest matches to the current pattern, and forecast from their continuations.
    Self-similarity turns 26 years into thousands of analogs.

## I. Construction improvements to the live winner (`deep:trend_switch_ens`)
43. **HRP on a multifractal distance.** Build the defense sleeve by hierarchical risk parity using
    an MF-DCCA distance.
44. **Tail-index-adjusted Kelly blend.** Set the offense/defense mix by stable-distribution growth
    rates instead of a binary trend vote.
45. **Volatility-clock rebalancing.** Tranches rebalance when cumulative realised variance crosses
    thresholds, not on days 0/5/10/15. Trading is dense in crises and sparse in calm.
46. **Momentum lookback in trading time.** 12-1 momentum is measured over a fixed amount of
    cumulative variance, not 252 days. After a crash the lookback shrinks automatically, which
    targets the known 2009 slow re-entry weakness.
47. **Regime trend in trading time.** The SPY trend votes (6–12 months) are measured over constant
    cumulative variance rather than constant days.
48. **Multifractal yield-curve duration choice.** Pick the defense sleeve's bond duration
    (SHY/IEF/TLT) by the Hurst exponent of yield changes at each maturity: persistent falling
    yields favour long duration.
49. **Transformer over VIX term structure and SPY scale features.** Forecast next-month SPY
    drawdown probability for the switch (^VIX/^VIX3M from 2007).
50. **Cascade-intensity offense sizing.** Scale the offense sleeve's breadth (top 3 vs top 8) by
    the current multifractal intermittency (λ²) of the ETF cross-section: concentrate when the
    cascade is quiet, diversify when it is intense.
