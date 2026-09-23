# alpha: fractal and transformer trading strategies, scored by CAGR

| path | what |
|---|---|
| `*.pdf` | source documents (Mandelbrot & Hudson; Borland et al.; Bouchaud; Wolfram) |
| `research/extracted/` | plain-text extraction of every PDF, with `[page N]` markers |
| `research/REVIEW.md` | review of all four documents and what they imply for strategies |
| `research/PLAN.md` | the sub-agent research plan and evaluation protocol |
| `data/` | `market_daily.csv` (1926–2026 daily total returns, Ken French library) + `fetch_data.py` |
| `harness/` | CAGR-only walk-forward harness (see `harness/README.md`) |
| `strategies/` | one directory per strategy |
| `results/` | `ledger.jsonl` (every harness run) and `leaderboard.md` |

## Quick start

```bash
uv venv .venv -p 3.11 && uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -q tests/
.venv/bin/python -m harness strategies/_example/strategy.py --benchmarks
```

## Results (final, CAGR only; full table in `results/leaderboard.md`)

Holdout = 2000-01-03 → 2026-07-31, sealed until every strategy was frozen and run exactly once.

| | holdout 2000–26 | dev 1950–99 | early 1932–49 |
|---|---:|---:|---:|
| **r2:construct_rank5_stag4** (49-industry 12-1 momentum, top fifth, rank-weighted, 4 staggered monthly tranches) | **13.03%** | 19.62% | 17.69% |
| plain 49-industry 12-1 momentum (top third, equal weight) | 12.18% | 17.58% | 15.97% |
| best round-1 strategy (12-industry momentum, tail-constrained) | 10.82% | 15.64% | 10.71% |
| buy & hold US market | 8.45% | 13.40% | 10.52% |

* Round 1 (7 agents: 4 fractal, 2 transformer, 1 hybrid) found one working idea, cross-sectional
  industry momentum. The fractal signals, market timing and transformers added nothing robust
  (`research/ROUND1_REVIEW.md`).
* Round 2 (5 agents) concentrated on that idea using a 49-industry universe. Every round-2 strategy
  beat buy & hold in the holdout, by 3.6–4.6 points a year.
* Caveat: the top strategy's worst drawdown was −61% against −55% for buy & hold, and it beat the
  market in only 14 of 27 holdout years.

## Round 3: tradeable ETFs only (`results/round3_etf.md`)

On a long-only universe of 56 real ETFs with per-ETF costs (holdout 2016–2026, sealed):
**r3:options_switch210_mom5_sharpe7** 16.90% vs SPY 14.99% and 60/40 9.58%, max drawdown −25.7% vs −33.7%.
It beat SPY in only 4 of 11 years, and its margin comes from 2022 and 2025. The other round-3
strategies beat 60/40 but not SPY. Covered-call ETFs didn't raise CAGR.
Live orders: `python -m harness.live strategies/r3_options/strategy.py --capital 100000 --refresh`.

## Deep dive (orchestrator, no subagents): `research/deep/REPORT.md`

**deep:trend_switch_ens** is a robust version of the round-3 winner: an ensemble of four trend lengths
switches between a momentum offense (top 5 ETFs) and a defensive book (top 7 by risk-adjusted
momentum). It beats SPY in every period tested:
* 1965–99 proxy: +6.1 points a year;
* 2000–15: +5.9;
* 2016–26 holdout: 16.08% vs 14.99%;
* 2000–26: 12.27% vs 8.27%, with max drawdown −39% vs −55%.
Recent-period edge is small, and 2016–26 alone is not statistically significant.
Live orders: `python -m harness.live strategies/deep_trend_switch/strategy.py --capital 100000 --refresh`.
