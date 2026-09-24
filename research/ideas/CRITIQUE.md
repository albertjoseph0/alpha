# Reviewer critique of the 50 ideas (sub-agent, review only)

**Verdict:** only two ideas look likely to add real CAGR out of sample, #47 and #46. Both measure lookbacks in trading time, which is a fractal idea, and neither uses a transformer. Both aim at the strategy's known weakness, slow re-entry after a crash. The transformer ideas all score low: they don't fix the actual problem, which is that 2000–15 contains only about 3 bear markets and about 2 re-entries to learn from. Making more views of the same data (augmentation, rescaled analogs, trading-time bars) doesn't add new events. Many of the fractal ideas repeat rounds 1–3.

Two facts shape the tests:
- **The ETF holdout is used up.** 2016+ has been looked at twice (round 3 and the deep dive), so it can't confirm anything any more. The regime-switch work never touched 1927–1964 on the French market data, so that is the cleanest window left for regime ideas.
- **The re-entry fix has barely been searched.** The switch only ever tried trend lengths of 126–252 days. Its re-entry weakness is a question of speed, and faster speeds are untested.

## 1. Scores (N novelty, P plausibility, T testability, O overfit, where 5 = low risk; Σ out of 20)

| # | N P T O | Σ | critique |
|---|---|---|---|
|1|3 1 3 2|9|Scale tokens are just HAR-style features; won't beat 12-1 on this little data|
|2|2 1 2 2|7|WaveToken (2024), wavelet leaders (Jaffard/Wendt). Wavelet edge effects leak the future|
|3|2 2 4 3|11|HAR (Corsi 2009), LogSparse attention. Amounts to a multi-lookback momentum|
|4|2 1 3 2|8|Volatility/dollar bars (López de Prado), Ané–Geman. Same clock as #46/#47, more complex|
|5|3 1 4 2|10|Adds no independent episodes. k^H rescaling is wrong under multifractality|
|6|3 1 3 2|9|Roughness again (`mf_spectrum`), SAX-like alphabet|
|7|3 1 3 2|9|Adaptive attention span (Sukhbaatar 2019) plus the Hurst gating that failed|
|8|3 1 3 2|9|`mf_spectrum` found spectrum width carries nothing beyond realized vol|
|9|2 1 3 2|8|Repeats `hurst_regime`|
|10|2 1 3 2|8|Hill estimator is noisy; repeats `tail_risk`|
|11|3 1 2 2|8|The "latest-position reconstruction" is a lookahead trap (wavelet boundary)|
|12|2 2 4 3|11|Kritzman absorption ratio (2011), effective rank. Works mostly at the same time as the crash, not before|
|13|4 1 1 1|7|Too vague to build; free-form tree fitting|
|14|2 1 3 1|7|Lead-lag (Hou 2007) is arbitraged away at daily frequency with a 1-day lag|
|15|2 1 4 3|10|MF-DCCA (Zhou 2008); the defense sleeve already ends up in Treasuries and gold|
|16|3 1 2 1|7|Scenario Kelly amplifies the generator's errors in expected returns|
|17|2 1 2 2|7|A volatility-timing gate; repeats `multifractal_vol`/`fractal_transformer`|
|18|4 1 3 3|11|Learns a trend t-stat; per-asset gates already failed|
|19|3 1 3 2|9|Flawed: IAAFT keeps the power spectrum, so it keeps the trend it is meant to detect|
|20|2 1 4 4|11|Amounts to t-stat or Sharpe momentum, i.e. the defense sleeve|
|21|2 2 4 4|12|Calvet–Fisher MSM; Markov-switching allocation (Kritzman 2012, Ammann)|
|22|3 1 4 3|11|Zumbach/Lynch–Zumbach causality: a weak stylized fact, not a timing signal|
|23|2 1 4 2|9|The repo's own Ĥ has sd 0.04–0.09; repeats `hurst_regime`|
|24|1 1 2 2|6|Deep LPPLS (Nielsen–Sornette–Raissi 2024). Offense earns *on* bubbles|
|25|1 1 3 1|6|Sornette LPPLS; unstable fits, weak out-of-sample record|
|26|1 1 3 2|7|Powerformer (2025), VORT (2026); architecture changes don't create alpha|
|27|1 1 4 2|8|López de Prado fracdiff; amounts to momentum with a power-law kernel|
|28|2 1 4 3|10|Gripenberg–Norros fBm predictor; returns have H≈0.5, so the forecast is ≈0|
|29|2 1 4 2|9|Learning-to-rank (Poh et al. 2021) on features already shown to be empty|
|30|2 1 5 4|12|Frog-in-the-pan (Da–Gurun–Warachka 2014); similar to the r2 winsorised/ruler tests|
|31|2 1 5 3|11|Local version of `mf_spectrum`; a Hölder exponent from ~10 points is noise|
|32|2 1 4 2|9|Costa multiscale entropy; no mechanism|
|33|3 1 3 2|9|Zumbach 2009 time-reversal; daily ETF data gives little signal|
|34|1 1 4 3|9|Standard robust loss, not a strategy|
|35|2 1 3 2|8|Momentum Transformer multi-horizon heads; forecast reconciliation|
|36|2 1 3 2|8|Training trick, not a source of edge|
|37|1 2 3 3|9|Transfer Ranking (Poh 2022), X-Trend (Wood 2023). The only transformer idea that adds real data|
|38|2 1 4 3|10|Giglio et al. 2008; daily sign sequences are essentially incompressible|
|39|3 1 3 2|9|Perplexity mostly tracks volatility shocks; vol timing already failed|
|40|3 1 3 2|9|Repeats #38/`token_gpt`|
|41|3 1 2 1|7|Very many degrees of freedom|
|42|2 1 3 1|7|Analogue method (Farmer–Sidorowich), X-Trend; rescaled analogs aren't independent|
|43|2 1 4 3|10|HRP (López de Prado 2016); the defense sleeve doesn't drive CAGR|
|44|2 1 4 2|9|Partial blends were already rejected ("full switching is monotonically best")|
|45|3 1 4 3|11|The switch weight is already daily; this only refreshes sleeve picks|
|46|3 2 5 3|13|Variable-length window, not the failed trading-time *z-score*|
|47|3 3 5 4|15|Close to Garg et al. 2023 dynamic speed, but new for this switch|
|48|3 1 3 2|9|The Sharpe sleeve already chooses duration|
|49|2 2 1 1|6|VIX3M only from about 2007, so the dev window has ~2 events|
|50|3 2 4 3|12|λ² adds nothing beyond realized vol; plausibly collapses to "always top-3"|

**Duplicates of earlier failed work:**
- `hurst_regime`: 7, 9, 23
- `mf_spectrum`: 6, 8, 31
- `tail_risk`, or partial blends already rejected: 10, 44
- volatility-timing work: 17, 39
- `token_gpt`: 40
- `r2_transformer`: 29
- `r2_fractal_momentum`: 30

**Duplicates of each other:**
- trading-time clock: 4, 45, 46, 47
- LPPLS: 24, 25
- same generator: 16, 17
- compressibility and perplexity: 38, 39, 40
- MF-DCCA: 15, 43
- surrogate nulls: 19, 20
- Hurst-shaped attention: 7, 26, 28
- "more data" tricks: 5, 37, 42
- wavelet tokens: 2, 11
- multiscale context: 1, 3
- intermittency λ²: 8, 50

## 2. Top 5

**#1 — Idea 47: SPY trend votes measured in trading time**
- **For:** It targets the documented weakness directly. After a crash, volatility is high, so a fixed variance budget spans fewer days and re-entry comes sooner (2009, 2020). It has one parameter, and 100 years of market data are available to test it.
- **Against:** It may just be "a faster trend", which Garg et al. already published. High volatility also shortens the window during corrections, which could make the 2011 whipsaw worse.
- **Test:**
  - Rule: for each L in {126, 168, 210, 252}, the budget is V_L = L × the trailing 10-year mean daily variance. The window is the shortest n (21–504 days) whose summed r² reaches V_L. Everything else stays as in `deep:trend_switch_ens`.
  - Compare against the base ensemble, and against a fixed-speed ensemble with the same average lookback that adds 63-day votes.
  - Windows: French market vs T-bills 1927–64 (not yet used for switch research), 1965–99 proxy, ETF 2000–07 and 2008–15.
  - Success: at least as good as the base in 4 of 5 windows, including 2008–15; paired block-bootstrap P(difference > 0) ≥ 0.8 over 1927–2015; beats the fixed-speed control.
- **Trap:** Normalizing the budget with the full-sample variance is lookahead. Tuning the window caps or the normalizer length is overfitting.

**#2 — Idea 46: 12-1 lookback in trading time, using SPY's variance clock**
- **For:** After a crash, 12-1 momentum holds last year's defensive winners (the Daniel–Moskowitz momentum crash). A shorter post-crash window picks the rebound leaders. It works together with #47.
- **Against:** Trading-time *normalization* already came out flat (15.94% vs 16.06%). Long-only momentum crashes cost less than the long-short versions in the literature.
- **Test:** Top-5 offense sleeve on 49 French industries in 1927–49, 1950–74 and 1975–99, then on ETF 2000–15 combined with #47. Compare against 12-1 and a fixed 6-1. Success: beats both in 3 of 4 windows, and in the pooled 12 months after major troughs.
- **Trap:** Using a separate clock per asset brings back the low-volatility tilt that hurt in r2. The skip month must also be measured in trading time.

**#3 — Idea 21: MSM slowest-component switch**
- **For:** The parameters come from the literature, it is cheap to run, and it can be tested on 100 years.
- **Against:** It is a volatility signal, and the slow component stays high after the market bottoms. That would make the 2009 re-entry worse. I expect it to fail.
- **Test:** Replace the trend fraction with P(slow component = high). Use k̄=8 and refit by maximum likelihood on an expanding window each year. Use the same windows and criteria as #1.
- **Trap:** Parameters estimated on the full sample, or a threshold tuned after the fact.

**#4 — Idea 12: correlation dimension or absorption ratio as a fifth vote**
- **For:** It measures a different quantity from price trend, and published crash evidence exists.
- **Against:** Correlations spike *during* crashes, not before them, and stay high after (slow re-entry again).
- **Test:** Effective rank of the 126-day correlation matrix of the 12 French industries, as a z-score against the trailing 2 years. Add it as a fifth ensemble vote and apply the #1 criteria.
- **Trap:** In the ETF universe, new listings mechanically change the rank. Use a fixed set of assets.

**#5 — Idea 50: breadth set by cascade intensity**
- **For:** Concentration raised CAGR in r2, so making it conditional is a natural next step.
- **Against:** λ² carried no information beyond realized volatility.
- **Test:** Must beat *every* fixed k in {3, 5, 8} across the four 49-industry and ETF windows.
- **Trap:** Choosing the median threshold after seeing the results.

If a transformer is attempted at all, make it #37, pretrained on 1926–99 data, with 12-1 as the only baseline. Its best-case score is still 9/20.

## 3. Missing idea that belongs in the top 5

**A Garg–Goulding–Harvey–Mazzoleni (JFE 2023) "rebound" state.** When the slow trend (126–252 days) is down but the fast trend (21–63 days) is up, go to offense. It is published, has almost no free parameters, and targets the 2009 re-entry directly. I would rank it #2. It is also the control #47 has to beat: if trading time doesn't beat this simple speed blend, the fractal part adds nothing.

Sources:
- [Momentum Turning Points (JFE 2023)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3489539)
- [Deep LPPLS](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4839066)
- [WaveToken](https://www.amazon.science/publications/enhancing-foundation-models-for-time-series-forecasting-via-wavelet-based-tokenization)
- [VORT power-law memory](https://arxiv.org/html/2605.08966v1)
- [Absorption ratio](https://portfoliooptimizer.io/blog/the-absorption-ratio-measuring-financial-risk/)
- [Markov-switching allocation](https://link.springer.com/article/10.1057/jam.2010.27)
- [MSM](https://en.wikipedia.org/wiki/Markov_switching_multifractal)
