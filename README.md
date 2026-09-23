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
