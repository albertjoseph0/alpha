# HANDOFF: how to resume this research in a fresh session

Everything in this project runs inside one Claude Code session: the orchestrator plus background research agents.
If that session ends (for example because its credits run out), all agents stop with it. A new session
can resume from the repository alone, using the steps below. Branch: `claude/gracious-brown-m9t9wj`.

## 1. Setup in a new session
* `uv venv .venv && uv pip install --python .venv/bin/python pandas numpy pyarrow yfinance torch scipy scikit-learn lightgbm`
  (or re-use an existing .venv). Downloaded data lives under `data/` and is git-ignored, so a new machine must
  re-download it. Every fetch script is idempotent and caches to disk.
* Jev (TypeSafe) is reached through the Vercel AI Gateway credential stored in the environment, which the proxy
  injects. Client: `research/round5/jev.py` (disk cache and per-agent budgets). SEC EDGAR: always use
  `research/round5/sec.py` (shared rate limit).
* Rules for all research: `research/round5/BRIEF.md` (+ `research/round6/BRIEF_JEV.md` for Jev agents).

## 2. Where everything stands
The results tracker is `research/round5/RESULTS_TRACKER.md`. Each agent folder has `STATUS.md` (what's done and
the exact next step), plus `PREREG.md` and `README.md` when finished.

| id | folder | idea | state |
|---|---|---|---|
| m01 | research/round5/m01_midcap_momentum | concentrated mid-cap momentum + trend switch | DEV done (17.4% vs 9.9% mkt, 1927–93); test and stock-level work pending |
| m02 | research/round5/m02_crypto_momentum | crypto momentum | **done: NO EDGE** (TEST −41.9%) |
| m03 | research/round5/m03_convex_trend_calls | long SPX calls + trend | stopped: DEV negative (see INTERIM_m03_m04.md) |
| m04 | research/round5/m04_tail_barbell | Taleb/Universa put barbell | **done: NO EDGE** (TEST −0.20 pts vs SPY) |
| m05 | research/round5/m05_insider_clusters | insider cluster buying + Jev footnotes | in progress |
| m06 | research/round5/m06_filing_reader | earnings releases: LM / FinBERT / Jev features | in progress |
| m07 | research/round5/m07_prediction_markets | Kalshi/Polymarket favourite–longshot | in progress |
| m11 | research/round5/m11_tree_ranker | boosted-tree stock ranker | in progress |
| j01 | research/round6/j01_lazy_prices | Lazy Prices 10-K changes + Jev | in progress |
| j02 | research/round6/j02_8k_events | 8-K material events + Jev | in progress |
| j03 | research/round6/j03_fomc | FOMC statements + Jev → ETF allocation | in progress |
| j04 | research/round6/j04_spinoffs | spin-offs + Jev-read Form 10 | in progress |
| j05 | research/round6/j05_ipo_quality | IPO prospectus quality + Jev | in progress |
| o01 | research/orch/o01_activist_13d | activist 13D Item 4 + Jev (orchestrator's own) | s01 listing running; s02–s04 written; next: s02 text, s03 prices, s04 Jev, then analysis |
| o02 | research/orch/o02_beige_book | Beige Book sector rotation + Jev (orchestrator's own) | s01 done (236 editions 1996–2026); s02_jev.py written (national summary, 12 sector-direction questions, probe); run it, then build a harness strategy (DEV etf_dev 2000–15, TEST etf_holdout 2016+) vs sector momentum and dictionary baselines |

The validated live strategy remains `strategies/deep_trend_switch/strategy.py` (see `research/deep/REPORT.md`).

## 3. To resume
For each agent whose README.md is missing: start a subagent with the prompt
"You are research agent <id> in /home/user/alpha, resuming after a session end. Read research/round5/BRIEF.md
(and research/round6/BRIEF_JEV.md for j0x), then your folder's STATUS.md, and continue from its next step.
Keep STATUS.md up to date; finish with README.md." Run at most 8–12 at once on a 4-CPU machine.
Then review the finished READMEs, update RESULTS_TRACKER.md, and launch the next round from
`research/round6/CANDIDATES.md`.
