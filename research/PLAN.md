# Plan: parallel strategy research with sub-agents

## Goal
Develop trading strategies grounded in the supplied documents: fractal/multifractal
finance (Mandelbrot, Bouchaud, Borland, Muzy, Zumbach) and transformers (Wolfram).
Score every strategy **only by CAGR**, through one harness with identical data,
frictions and walk-forward rules.

## Shared infrastructure (built before any agent starts)
| piece | location | purpose |
|---|---|---|
| extracted texts | `research/extracted/*.txt` | full text of all 4 PDFs with `[page N]` markers; nobody re-parses PDFs |
| review | `research/REVIEW.md` | the digest of all documents, with page pointers; every agent reads this first |
| data | `data/market_daily.csv` | 100 years of daily total returns: US market + 12 industries + T-bills (Ken French library) |
| harness | `harness/` (`README.md`) | walk-forward runner, causality audit, cost/lag/leverage rules, CAGR |
| env | `.venv/` | numpy, pandas, scipy, statsmodels, scikit-learn, PyWavelets, torch (CPU) are pre-installed |

## Evaluation protocol
1. Agents iterate **only** on the `dev` window (1950–1999), optionally checking
   `dev_a`/`dev_b` halves for stability. Research reads data via `harness.load_dev()`.
2. Each agent submits **exactly one** final strategy (`strategies/<dir>/strategy.py`).
   Selecting the best of many variants inflates dev CAGR; the holdout corrects for it.
3. The orchestrator runs the **sealed holdout** (2000-01-01 → 2026-07-31) once per
   final strategy, in the same code path, and publishes `results/leaderboard.md`
   ranked by holdout CAGR, next to dev CAGR and the benchmarks.

## Agent roster (7 agents, same model and permissions as the orchestrator)

Fractal-mathematics family:

| # | agent | directory | core idea (documents) |
|---|---|---|---|
| 1 | Joseph effect: long memory | `strategies/hurst_regime/` | Rolling Hurst exponent (R/S, DFA, variance-time; Lo-robust) to switch between trend and mean-reversion/defensive per asset and across industries. Book ch. IX–X; Notes p. 326. Must handle stale-price bias. |
| 2 | Multifractal volatility and trading time | `strategies/multifractal_vol/` | Forecast volatility with MSM (Calvet–Fisher), MRW log-vol kernel, or Zumbach/Borland multi-timescale ARCH with leverage (g₁<0). Size exposure and allocate by forecast vol; momentum measured in *trading time*. Borland et al. eqs. 10–15; heresy 9. |
| 3 | Noah effect: tails and crash avoidance | `strategies/tail_risk/` | Rolling Hill/tail-index α, tail dependence across industries, "tail chiseling" portfolio (Bouchaud et al. 1998), market-shock "Richter" index; de-risk when tails and co-crash risk rise. Book ch. VIII, heresies 2/3/7/9, ch. XIII. |
| 4 | Multifractal spectrum signals | `strategies/mf_spectrum/` | Rolling MF-DFA / wavelet-leader estimates of ζ(q), intermittency λ², singularity-spectrum width; turbulence/regime indicator and multi-scale cascade asymmetry (Zumbach mug-shots) for timing and allocation. Book ch. XI; Borland et al. §3, §5.4. |

Transformer family:

| # | agent | directory | core idea (documents) |
|---|---|---|---|
| 5 | Tokenised next-token GPT | `strategies/token_gpt/` | Wolfram-style: discretise vol-normalised returns into a token vocabulary, train a small causal transformer on next-token prediction, decode the predictive distribution (temperature) into positions. |
| 6 | End-to-end transformer allocator | `strategies/transformer_allocator/` | Attention over time × assets outputs portfolio weights directly, trained to maximise mean log growth (the in-sample CAGR objective) under Σ\|w\| ≤ 1, with strong regularisation and ensembling. |

Hybrid:

| # | agent | directory | core idea (documents) |
|---|---|---|---|
| 7 | Fractal-pretrained transformer | `strategies/fractal_transformer/` | Pretrain on large synthetic multifractal markets (MMAR / MRW / fBm-in-multifractal-time "forgeries"), fine-tune on real dev data; and/or fractal features (H, α, λ², multi-scale vols) as token embeddings. Tests Wolfram's "simulated data" lore against Mandelbrot's generators. |

## Rules every agent follows (restated in each agent's prompt)
* Read `research/REVIEW.md` and `harness/README.md` first. Consult `research/extracted/*.txt`
  (grep `[page N]`) instead of the PDFs. Don't read the whole book: jump to cited pages.
* Write only inside your own `strategies/<dir>/`. Don't modify `harness/`, `data/`,
  `tests/`, `research/`, or other agents' directories. No git commands.
* Only dev data. Never run `--window holdout`, never set `ALPHA_HOLDOUT`, and never read
  post-1999 rows of the CSV. Don't hard-code knowledge of historical events or dates.
* CPU budget: 4 shared cores, no GPU. Set `torch.set_num_threads(1)` and
  `OMP_NUM_THREADS=1`. The final strategy's full dev run should finish in about 20
  minutes or less, since the holdout run is similar in length.
* Deliverables in `strategies/<dir>/`:
  * `strategy.py`: the one final strategy.
  * `README.md`: hypothesis with document citations, method, parameters, dev / dev_a /
    dev_b CAGR, what was tried (including failures), the number of dev evaluations run,
    runtime, and known risks.
  * `result_dev.json`: written by the harness CLI.
  * Optional: `research/` scripts.
* If you think the harness is wrong, say so in your report. Don't modify it.

## After the agents finish
1. Run `pytest` and a dev re-run of each final strategy (reproducibility plus causality audit).
2. Holdout run of each final strategy (`ALPHA_HOLDOUT=1`), once.
3. `python -m harness.leaderboard` → `results/leaderboard.md`; commit and push.

---

# Round 2 plan (after `research/ROUND1_REVIEW.md`)

**Principle: power law.** Round 1 found exactly one working idea: cross-sectional industry
momentum. Round 2 puts all of its agents on it. Each agent attacks a different angle of
**momentum on the 49-industry universe** (`i49_*` assets, added to the harness for this round).

**Baseline to beat.** This is plain 12-1 momentum, top third, equal weight, monthly
(`research/round1/breadth_check.py`). It scores dev 17.58%, dev_a 15.08%, dev_b 19.98%,
early 15.97%. A round-2 strategy must beat buy & hold in *every* window (dev_a, dev_b, early),
and should beat this baseline.

| # | agent | directory | angle |
|---|---|---|---|
| 1 | Signal engineering | `strategies/r2_signal/` | lookback ensembles, skip-month, residual (beta-adjusted) momentum, 52-week-high proximity, industry-size effects |
| 2 | Fractal momentum refinement | `strategies/r2_fractal_momentum/` | path smoothness (ruler / fractal dimension), jump-filtered momentum (Joseph not Noah), trading-time normalisation, per-industry persistence |
| 3 | Portfolio construction | `strategies/r2_construction/` | holdings count, score / rank weighting, rebalance frequency, turnover buffers and hysteresis, weight caps, log-growth sizing |
| 4 | Crash-robust momentum | `strategies/r2_crash_guard/` | handle loser rebounds after bear markets *while staying invested*: dynamic momentum, fallback to the market or equal weight, dual momentum |
| 5 | Transformer cross-sectional ranker | `strategies/r2_transformer/` | attention over the 49 industries (no identity embeddings) with momentum-family features, trained on log growth; ensembled with the rule baseline |

---

# Round 3 plan: tradeable strategies only (3 agents)

Rounds 1–2 were scored on academic portfolios that can't be bought. Their ETF translation lost
most of its edge (`strategies/etf_momentum/`). Round 3 therefore scores **only** on a tradeable,
long-only ETF universe with per-ETF costs, and every strategy must produce live orders through
`harness.live`.

* Development: `etf_dev` 2000–2015 (halves `etf_dev_a`, `etf_dev_b`). Holdout: 2016 → today, sealed.
* The long 1926–1999 academic data may be used only for idea discovery.
* **Bar:** beat both SPY and 60/40 in `etf_dev_a` **and** `etf_dev_b`, net of costs.
* **Baseline** (`strategies/_example_etf`: top-5 12-1 momentum across all ETFs, monthly): dev 8.91%,
  dev_a 14.07%, dev_b 4.01%. It fails dev_b (SPY 6.46%).

| # | agent | directory | angle |
|---|---|---|---|
| 1 | Cross-asset momentum and trend | `strategies/r3_cross_asset/` | rotation across all asset classes, using round-2 construction lessons (rank weights, staggered tranches) and trend rules that rotate to bonds or gold rather than cash |
| 2 | Equity rotation | `strategies/r3_equity_rotation/` | momentum within the equity sleeve (sectors, industries, countries, styles) with the same lessons, tested on real ETF breadth |
| 3 | Option-income and defensive sleeve | `strategies/r3_options/` | whether covered-call / buy-write ETFs, low-vol and other defined-risk funds raise CAGR, alone or combined with a momentum core |
