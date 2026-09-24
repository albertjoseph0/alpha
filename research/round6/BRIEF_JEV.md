# Round 6 brief: Jev-first strategies (read fully, together with research/round5/BRIEF.md)

The user wants this round focused on **Jev** (TypeSafe's System One evaluation model, reached through the
Vercel AI Gateway), because it's new technology. Every round-6 agent builds a strategy in which Jev is
the key ingredient. Jev turns unstructured text into calibrated, typed numbers that a small model trained
on DEV then turns into trades.

All rules in `research/round5/BRIEF.md` apply: tradeable, long-only or bounded downside, no lookahead,
explicit costs and 2× costs, survivorship handling, PREREG.md, a sealed TEST run once, the report format
and verdicts, and resource etiquette. You also keep STATUS.md up to date, don't git commit, and don't
spawn subagents. Your folder is `research/round6/<id>/`; your data folder is `data/round6/<id>/`.

## Tools
* **Jev:** `sys.path.insert(0, "research/round5"); from jev import ask, spent`. See jev.py's docstring for
  question formats. Score criteria are a list; choice criteria are a dict. Pass `agent="<your id>"`.
  Budgets: j01 $8, j02 $5, j03 $1, j04 $2, j05 $3. Responses are cached, so re-runs are free. Batch many questions
  into one call per document (one state, many questions), which is much cheaper than one call per question.
* **SEC EDGAR:** `from sec import get` (research/round5/sec.py). It is a shared, cross-process rate-limited
  fetcher with a disk cache. **Always use it for sec.gov**: several agents share one IP, and the SEC blocks
  IPs above 10 requests/s.
* Prices: yfinance. Point-in-time S&P 500 intervals from 2019-10 are in
  `data/round5/m06_filing_reader/sp500_pit_intervals.csv`; m11 is rebuilding membership from 2011-12
  (read-only).

## Required experimental design (what makes a Jev result credible)
1. **Three nested feature sets on identical events and dates:** (a) no text (price or event data only);
   (b) a cheap text baseline without an LLM (Loughran–McDonald dictionary, cosine similarity, or keyword
   rules); (c) the same plus Jev features. Jev "works" only if (c) beats (b) out of sample.
2. **Factual questions only.** Ask what the document says ("does the risk-factor section add a new going-concern
   risk?"), never what will happen. Remove company names, tickers and exact dates from the state where
   feasible.
3. **Leakage probe.** On a sample of about 200 DEV documents, ask Jev a *forbidden* question such as "Did this
   company's stock outperform the market over the following 12 months?" and measure its accuracy against the
   realized outcome. If it beats chance clearly (e.g. AUC > 0.55), Jev may know outcomes: report it, and
   treat the backtest as contaminated for that period. Report the probe result either way.
4. **Pre-register the question list.** Freeze the questions and the model before TEST. You may iterate on
   questions during DEV only, and must log every question set tried (keep this small).
5. Report: Jev tokens and cost used, calls, confidence distribution, and which questions mattered (feature
   importance or ablation).
