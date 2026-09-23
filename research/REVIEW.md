# Review of the source documents

Four documents were supplied. All were converted to plain text (page markers preserved)
in **`research/extracted/`**; grep for `[page N]` to jump to a page. Nobody needs to parse
the PDFs again.

| file | document | pages |
|---|---|---|
| `mandelbrot_origins_of_econophysics.txt` | J.-P. Bouchaud, *Mandelbrot, Financial Markets and the Origins of "Econophysics"* (arXiv:2602.02078, Feb 2026) | 11 |
| `dynamics_of_financial_markets.txt` | L. Borland, J.-P. Bouchaud, J.-F. Muzy, G. Zumbach, *The Dynamics of Financial Markets — Mandelbrot's Multifractal Cascades, and Beyond* (cond-mat/0501292, 2005) | 24 |
| `misbehavior_of_markets_mandelbrot.txt` | B. Mandelbrot & R. Hudson, *The (Mis)behaviour of Markets: A Fractal View of Risk, Ruin and Reward* (2004) | 360 |
| `what_is_chatgpt_doing_wolfram.txt` | S. Wolfram, *What Is ChatGPT Doing … and Why Does It Work?* (2023) | 125 |

Three documents cover fractal and multifractal finance, and one covers transformers. Below is
a document-by-document review, then the synthesis that drives the strategy plan
(`research/PLAN.md`).

---

## 1. Mandelbrot & Hudson — *The (Mis)behaviour of Markets* (2004)

A popular-science book in Mandelbrot's voice, arguing that orthodox finance (Bachelier,
Markowitz, Sharpe, Black–Scholes) assumes "mild" randomness while markets have "wild"
randomness. Mathematics is in the Notes (pp. 305–330 of the PDF). The book is explicit
that it is not a trading manual: *"This book will not make you rich"* and *"it is premature
to be hoping for serious gains from fractal finance"* (PDF p. 289).

### Part I — the old way and the case against it (PDF pp. 31–135)
* **Three states of randomness** (p. 60–61). *Mild* is Gaussian: many small independent
  contributions. *Wild* is Cauchy-like: the largest event is comparable to the sum of all
  others. *Slow* sits in between. Markets are wild.
* **Evidence against the bell curve** (p. 41, 121–125). Dow 1916–2003: 1,001 days
  moved more than 3.4% against 58 predicted; 366 days more than 4.5% against 6 predicted;
  48 days more than 7%, where the prediction is one per 300,000 years. The 1987 crash was
  −29.2% (more than 20σ). S&P 500 daily kurtosis was 43 over 1970–2001 (7.2 without
  1987). Fama found moves beyond 5σ happen 2,000× more often than Gaussian odds. FX: a
  one-day dollar/yen fall of 7.92% (10.7σ).
* **Dependence** (pp. 126–128). Short-term momentum: Jegadeesh–Titman 6-month
  winners minus losers earned +12%/yr, reversing after about 2 years. Long-horizon
  reversal: Fama–French, 3–8 years. Mandelbrot distrusts both: *"when a statistician
  finds a result he had been expecting…"*
* **Anomalies** (pp. 129–130): P/E, small-firm-in-January, book-to-market. Fama–French
  1992, "beta is dead".
* **Trend following that works on paper** (p. 110). A Citigroup analysis of a 69-day
  moving-average rule on dollar/yen earned 7.97%/yr, "with hair-raising losses" along the
  way. More than half of FX speculators trend-follow.
* **LTCM** (pp. 133–135): leverage of 50:1 on Gaussian models. Meriwether afterwards:
  *"Our whole focus is on the extremes now."*

### Five rules of market behaviour (pp. 48–50)
(I) markets are risky; (II) trouble runs in streaks (volatility clusters); (III) markets have a
"personality": prices are driven by *endogenous*, *stationary* mechanisms; (IV) markets
mislead, because chance alone creates convincing trends and cycles; (V) market time is relative,
running fast in volatile periods and slow in calm ones ("trading time").

### Part II — the fractal toolkit (pp. 139–250)
* **Fractals, self-affinity, dimension** (pp. 151–173). Box-counting dimension
  `D = lim log N(r) / log(1/r)` (Notes p. 320–321). Price charts are *self-affine*: they
  scale differently in time and in price.
* **Cartoons** (pp. 146–148, 198–200, 222–223, 237–244). These are recursive generator
  constructions. The Brownian cartoon has generator vertices (0,0)→(4/9,2/3)→(5/9,1/3)→(1,1),
  so width = height², i.e. H = ½. Shuffling generator pieces adds randomness. Vertical
  jumps in the generator give power-law tails (the **Noah effect**). A generator with
  height = width^H gives long memory (the **Joseph effect**).
* **Cotton (Ch. VIII, pp. 175–200)**. Price changes have power-law tails with
  **α ≈ 1.7** (L-stable), and the *same* at daily and monthly scales. Sample variance of
  cotton price changes never settles, roaming 0.4%–3%. Pareto α for incomes is about
  1.5–2; Swedish fire claims have α ≈ 4. The L-stable characteristic function is in the Notes (p. 324).
* **Long memory (Ch. IX, pp. 201–223)**. Hurst's reservoir range grows like N^0.73, not
  N^0.5. The Hurst exponent **H** gives: 0.5 = independent, above 0.5 = persistent,
  below 0.5 = anti-persistent. Model: fractional Brownian motion (Mandelbrot–Van Ness 1968). The
  **R/S statistic** is in Notes p. 326–327. Reported H values: call money 0.7; wheat and UK
  bonds 0.5; Apple 0.75, Xerox 0.73, IBM 0.72, Anheuser-Busch 0.64, Texas Utilities 0.54
  (Peters); 18 USD FX pairs 0.53–0.63; S&P 500 0.53–0.74 depending on study. **No
  consensus.** Lo (1991) showed R/S confounds short- and long-memory. Hence *"never
  publish any result based on a single tool"* (p. 220).
* **Noah + Joseph (Ch. X, pp. 225–234)**. α measures the jumps and H the persistence. R/S
  compares the data with a shuffled copy to separate them. In some models H = 1/α. **Bubbles**:
  a Joseph "almost-trend" breaks as a Noah discontinuity. See the toy model with weather-driven
  wheat value and an overshooting price, and Cisco 1998–2001.
* **Multifractal trading time (Ch. XI, pp. 235–250)**. MMAR (Multifractal Model of Asset
  Returns) is *fractional Brownian motion in multifractal trading time*: price = B_H(θ(t)).
  θ(t) is a multiplicative cascade, e.g. a binomial measure that recursively splits mass 60/40.
  The "Baby theorem" builds it from a "mother" (price as a function of trading time) and a "father"
  (clock time mapped to trading time). Tests by Calvet & Fisher: DM/$ (1.47M ticks 1992–93;
  daily 1973–96) scales from about 2 hours to 180 days, with crossovers outside that range. ADM,
  Lockheed, Motorola and UAL are "textbook multifractals"; GM, a US index and $/yen scale over
  a narrower range. It predicts kurtosis fading at long horizons. Mandelbrot criticises GARCH as
  ad hoc: parameters fitted on daily and weekly data give series of different character (p. 328).

### Part III — Ten heresies and "In the Lab" (pp. 253–304)
1. Markets are turbulent. 2. They are riskier than theory says. Ruin odds are 1-in-10 to
1-in-30 under wild variation against 10⁻¹⁹ under Gaussian (pp. 258–261); the equity premium
"puzzle" dissolves. 3. **Timing matters, and returns concentrate.** 46% of the 1986–2003
USD/JPY decline happened on 10 of 4,695 days; 40% of 1980s S&P gains came on 10 days
(pp. 261–263). 4. **Prices leap.** Alexander's 5% filter rule claimed 36.8%/yr on
closing prices and vanished once realistic fills were used (pp. 263–266). The lesson is to
never assume you trade at the price that triggered the signal. 5. Time is flexible. 6. Markets
in all places and ages work alike (invariance, stationarity). 7. Uncertainty and bubbles
are inevitable. The "Land of Ten Thousand Lakes" parable: under power-law scaling, after
travelling 5 miles you should still expect 5 more (conditional exceedance scales). 8. Markets
deceive. Slutzky: fBm with H ≈ 0.75 looks cyclical, e.g. Kondratieff waves. 9. **You cannot
forecast prices, but you can forecast the odds of volatility.** The martingale property roughly holds; magnitudes
are dependent while signs are uncorrelated ("dependence without correlation"). Market-shock
"Richter scales" include Maillet–Michel's IMS and Zumbach et al.'s index, which gave early
warning in Oct 1998 (pp. 275–277). 10. "Value" has limited value; arbitrage of price differences
drives markets.

**In the Lab** (pp. 281–304):
* **Olsen/OANDA**: "heterogeneous markets". Traders on many horizons meet at one price.
  Trade when short-horizon traders move *against* long-horizon investors.
* **Bouchaud/CFM**: a mean-reversion "center of gravity" signal plus **"tail chiseling"**
  (Bouchaud et al. 1998). Build portfolios that minimise the probability of simultaneous
  crashes under power-law tails, giving a "generalized efficiency frontier".
* **Fractal fingerprints**: driven iterated function systems (IFS) as a visual taxonomy of assets.
* **Portfolios**: under wild variation you need 3–4× more stocks for diversification (Fama
  1965). Conventional betas were underestimated by about 6% on nine Paris stocks.
  Monte-Carlo stress tests should become standard.
* **Options/risk**: the smile falsifies Black–Scholes. Variance-gamma (a time change plus
  Brownian motion) is used at Morgan Stanley. VaR under a Gaussian ignores the "overhang".
  Extreme Value Theory is better but ignores long dependence. Scholes, after LTCM: *"stress
  tests … more important than VaR."*

---

## 2. Borland, Bouchaud, Muzy, Zumbach — *The Dynamics of Financial Markets* (2005)

A technical review with the formulas needed to implement multifractal volatility models.

* **Stylized facts (pp. 3–5)**. (i) Return variance grows linearly with horizon, so
  returns are nearly uncorrelated. Tails follow |r|^(−1−μ) with **μ ≈ 3–5** for liquid
  markets (μ < 2 only in emerging markets), so the pure Lévy-stable hypothesis is rejected.
  Distributions become near-Gaussian at horizons of months. (ii) **Volatility clustering**: the
  autocorrelation of |r| decays as a power law with exponent **0.1–0.3**. (iii) **Multifractal
  scaling**: M_q(τ) = ⟨|r_τ|^q⟩ ∝ τ^ζ_q with concave ζ_q. For the S&P 500,
  ζ_q = q(½+λ²) − λ²q²/2 with **λ² ≈ 0.03** over about 3 decades of scale.
  (iv) **Leverage effect**: past returns are negatively correlated with future volatility, which
  gives negative skew.
* **Cascade (pp. 7–8)**. σ_{sτ} =ᵈ W_s σ_τ; the log-volatility is a sum of many i.i.d. terms,
  hence log-normal; Var[ln σ_τ] = −λ² ln τ + V₀.
* **Multifractal Random Walk, Bacry–Muzy–Delour (pp. 8–10)**. r_i = σ₀ e^{ξ_i} ε_i with Gaussian
  ξ, Cov(ξ_i, ξ_j) = λ² ln(T/τ₀) − λ² ln(|i−j|+1) for |i−j|τ₀ ≤ T, and mean
  −λ² ln(T/τ₀). The integral time T is a few years. It has a **causal form**: log-vol is a
  sum of past shocks with kernel ∝ 1/√lag. Log-covariance of log-vol is observed empirically,
  and the slope is roughly consistent with λ².
* **Failures (pp. 10–13)**. The MRW predicts μ = 1/λ² ≈ 33 (observed 3–5, though ergodicity
  breaking helps). It is time-reversal symmetric, while real data are not. Zumbach's
  "mug shots" show that **past volatility at long horizons drives future volatility at short
  horizons**, with peaks at intraday, 1-day, 1-week and 1-month horizons.
* **Multi-timescale ARCH / statistical feedback (pp. 13–14)**.
  σ²_i = σ₀² + Σ_k K(k) G(r̃_{i,k}), with r̃_{i,k} = (x_i − x_{i−k})/√(kτ₀) and
  G(r) = g₁r + g₂r² + … **g₁ < 0 reproduces the leverage effect**, and a power-law K(k)
  reproduces long memory and apparent multifractality. The justification is heterogeneous
  agents with horizon-dependent thresholds (stop-losses, entry points). This form is at odds
  with the efficient-market hypothesis.
* **Use (p. 15)**. These models are good at *volatility filtering and forecasting*
  (Calvet–Fisher MSM, Lux GMM, GARCH-like). Pricing needs Monte Carlo conditional on the price path.

## 3. Bouchaud — *Mandelbrot, Financial Markets and the Origins of Econophysics* (2026)

A methodological essay. Its load-bearing claims:
* Tails are fat but **not Lévy-stable**. Moments exist; cutoffs and regime shifts matter
  (p. 4).
* **Returns are nearly uncorrelated; volatility is not.** Its long memory is "the real
  empirical fact" (pp. 3, 5).
* **Most big jumps come "from nowhere"**, with no identifiable news. Market endogeneity
  (liquidity, leverage, positioning, herding) amplifies small shocks (p. 5).
* MRW (r = σε with long-range-correlated log σ) moves the explanatory burden from returns
  to volatility (p. 6).
* **Rough volatility**: vol is rougher than Brownian, with H < ½ at short scales; MRW is the
  H → 0 limit (p. 7).
* **Wavelet multi-scale models generate realistic synthetic series** (Morel–Mallat–Bouchaud,
  *Path shadowing Monte Carlo*, 2024). *"The goal of high-quality synthetic series is … stress
  testing, benchmarking of strategies"* (p. 7).
* Self-organised criticality: "efficient" markets can be fragile (p. 9). The warning:
  *"The current fashion for power laws, multifractals, or rough volatility can become
  superficial if it is not disciplined by empirical rigor"* (p. 9).

## 4. Wolfram — *What Is ChatGPT Doing … and Why Does It Work?* (2023)

A first-principles explanation of large language models and transformers.
* **Next-token prediction** (pp. 10–16). A model outputs a probability distribution over
  the next token. Always taking the argmax ("zero temperature") gives flat, repetitive text;
  sampling at **temperature** 0.8 works better. Token rank-frequency follows a power law
  (∝ n⁻¹, Zipf). This is the same mathematics as Mandelbrot's thesis on word frequencies (book p. 179).
* **Why a model and not a table** (pp. 17–23). The n-gram space explodes combinatorially, so
  one needs a parametric model that generalises. *"There's never a model-less model."*
* **Neural nets and training** (pp. 27–51). Weights and activations define attractor
  basins; the loss is minimised by gradient descent with backprop. Many weight settings fit
  the data equally well **but extrapolate differently** (p. 44). Lore: end-to-end training
  usually beats hand-crafted features for "human-like" tasks; **data augmentation and
  simulated data** help; transfer learning; loss curves plateau; power-law scaling laws.
* **Computational irreducibility** (pp. 52–55). There is a trade-off between trainability
  and computational capability. Nets capture regularities humans might notice, not
  irreducible processes. Per token, the transformer is feed-forward.
* **Embeddings** (pp. 56–62). Nearby vectors mean similar things. Embeddings are learned as a
  by-product of prediction tasks, and the pre-softmax layer is a usable embedding.
* **Inside the transformer** (pp. 63–71). Token embedding plus positional embedding are added
  together, then fed through a stack of attention blocks (multi-head attention "looking back"
  over the sequence) and fully-connected layers. The last position's vector is decoded by a
  softmax over the vocabulary.
* **Training scale and limits** (pp. 72–82). Weights number roughly as many as training tokens. A
  small transformer learns balanced parentheses up to some depth, then fails: it is *too
  computationally shallow*. For transformers, *"showing yet more examples just seems to degrade
  its performance"* (overfitting). RLHF and in-context learning are also covered.
* Pages 99–123 argue for pairing LLMs with precise computational tools (Wolfram|Alpha).

---

## 5. Synthesis: what the documents imply for CAGR-maximising strategies

**What the evidence says is (and isn't) forecastable**
1. *Direction* of returns is close to a martingale (Mandelbrot heresy 9; Bouchaud p. 5;
   Borland et al. fact (i)). Expect little from pure sign prediction, including from a
   transformer. Wolfram's own framework says nets capture learnable regularity, not
   irreducible randomness.
2. *Magnitude* (volatility) **is** forecastable. It has long memory, a multi-scale cascade
   from long horizons to short, a leverage effect, and log-normal-like distribution. This
   is the most robust, well-documented structure across all three finance documents.
3. *Tails* are power-law (μ ≈ 3–5 daily for liquid indices), and big moves cluster.
   Gains and losses concentrate in a few days (heresy 3).
4. Weaker, contested structure: medium-horizon momentum and trend (Citigroup MA,
   Jegadeesh–Titman), long-horizon reversal, persistence H > ½ in some series. Every such
   estimate is fragile (H estimates ranged 0.53–0.74 for the same index).

**Why these matter for CAGR under the harness's constraints (no leverage, Σ|w| ≤ 1)**
* CAGR ≈ arithmetic mean − σ²/2. Cutting exposure when volatility is forecast high
  (vol-targeting) lowers variance drag. Because of the leverage effect, high-vol regimes
  also tend to carry negative drift, so avoiding them can raise CAGR, not only lower risk.
* Missing the few best days is costly (heresy 3), so de-risking must be *selective*.
  Over-trading pays costs, and the one-day lag makes very fast signals useless.
* The industry panel adds cross-sectional choices: tail-dependence-aware allocation
  ("tail chiseling"), cross-industry momentum, and inverse-vol weighting.

**Pitfalls the data already exhibit (all measured on `data/market_daily.csv`)**
* **Stale-price autocorrelation.** Lag-1 autocorrelation of daily market returns is
  +0.13 to +0.29 in the 1940s–1980s and *negative* after 2000. With no execution lag, "buy if
  yesterday was up" gives +28% CAGR in 1950–99 and −20% in 2000–26. The harness imposes a
  one-day lag. Hurst and other persistence estimators on daily data are biased upward in
  exactly the dev period (Lo 1991). Use horizons of weeks or more, or pre-whiten.
* **Spurious patterns.** fBm with H ≈ 0.75 produces convincing but fake cycles (heresy 8).
* **Execution realism.** Alexander's filter lesson (heresy 4): signal price ≠ fill price.
* **Single-metric overfitting.** CAGR is noisy: with ~15% vol over 50 years, the standard
  error of the annualised mean is about 2%. Selecting the best of many variants inflates dev
  CAGR. The sealed holdout (2000–2026) is the arbiter.
* **Regime change.** The holdout differs from the dev period (sign of autocorrelation, lower
  rates, two 50% drawdowns). Robust mechanisms beat fitted ones.

**Transformers, per Wolfram, mapped to markets**
* Tokens are discretised (vol-normalised) returns; the rank-frequency of such tokens is itself
  power-law. The next-token softmax is a predictive distribution, and sampling temperature
  maps to how aggressively the distribution is turned into a position.
* Embeddings of market states give a learned "meaning space" of regimes.
* Data scarcity is severe: about 25k daily observations against billions of tokens for LLMs.
  Wolfram's lore suggests *simulated data / augmentation*, and Mandelbrot and Bouchaud supply
  exactly the simulators (MMAR, MRW, wavelet-scattering "forgeries") that reproduce
  fat tails, clustering and multi-scaling. Pretraining a transformer on synthetic multifractal
  markets, then fine-tuning on real data, is the natural bridge between the two literatures.
* Attention is a learned kernel over the past. Borland–Bouchaud's multi-timescale ARCH is
  a hand-specified kernel over past returns at many horizons, which is a natural baseline and
  inductive bias for a volatility-forecasting transformer.
