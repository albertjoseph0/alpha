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
