# m06 filing reader: PRE-REGISTRATION (written 2026-09-24 ~11:33 UTC, before any TEST model run)

## Question
Do the words in S&P 500 earnings press releases (8-K Item 2.02, EX-99) predict 3-month excess returns well enough
to beat SPY by 20 pts/yr, and does Jev (typed LLM reading) add anything over price features, a
Loughran-McDonald dictionary and FinBERT, on identical events?

## Frozen rule (code: `s06_events.py`, `s08_model.py` as of this file; no edits after this point)
* Events: 8-K 2.02 filings while the firm was in the point-in-time S&P 500. Acceptance time -> entry = first
  open after the release (<= 09:15 ET same open, otherwise next open). Features known by the entry-day close.
* Features: PRICE = gap_x, day0_x, mom_12_1, mom_1m, vol60. DICT = LM tone/pos/neg + change vs the previous
  release. FINBERT = ProsusAI/finbert (2020-12 weights) on the first 10 narrative sentences + changes.
  JEV = 28 frozen factual questions (`jev_questions.py`) on the anonymised current + previous release.
  Each feature is converted to a within-entry-month percentile rank (NaN -> neutral).
* Label: 63-trading-day return from the open AFTER the entry day, minus SPY; y = above the entry-month median.
* Model: primary logistic regression (C=0.1); secondary HistGradientBoosting (depth 3, 200 iters, lr 0.05,
  min leaf 200). Final models are fit on all DEV events whose label ended by 2022-12-30.
* Portfolio: first trading day of each month, among firms whose latest release entered within the last 63
  trading days, buy the top 40 by model score, equal weight, hold one month. Trade at the open.
* Costs: 10 bp per side on turnover (commission + half spread + slippage for S&P 500 names); also 20 bp (2x).
* Benchmark: SPY (dividend-adjusted). Control: equal-weight all eligible names (no skill).

## TEST runs (each run exactly once)
1. `s08_model.py test full`: price / +LM / +FinBERT / +LM+FinBERT (and text-only) on all TEST events;
   rebalances 2023-01 .. 2026-09. Model trained on all DEV events 2020-01..2022-12.
2. `s08_model.py test jev`: identical-events comparison price / +LM / +FinBERT / +Jev / all / Jev-only, trained on
   the Jev-scored DEV events (2020-01..2021-06) and applied to Jev-scored filings 2022-10..2023-12 (IC on 2023
   filings; rebalances 2023-01..2024-01). If the Jev gateway is too slow to finish, the TEST sample is cut to
   filings through 2023-06-30 (rebalances 2023-01..2023-07). This cut is decided on elapsed time only.
3. `s10_leak_probe.py` (Jev memorisation probe; not a feature).

## Primary strategies and success criteria
* Verdict strategy (full sample): `s_logit_price+dict+finbert`. MOONSHOT CANDIDATE if TEST CAGR after 10 bp
  costs beats SPY by >= 20 pts/yr; REAL BUT SMALLER if it beats SPY and the equal-weight control, and the
  monthly rank IC is > 0 with Newey-West t > 2; otherwise NO EDGE.
* Jev question: Jev adds value only if on identical TEST events `s_logit_price+jev` has a higher IC than
  `s_logit_price` AND its own IC has NW t > 2 AND its CAGR beats both `s_logit_price` and the control.
* Leakage probe: a forward-looking Jev answer with |IC| > 0.1 and |t| > 2 vs realised ar_63 in either period
  would mean Jev features cannot be trusted in backtests.

## What DEV already showed (so expectations are set honestly)
* DEV full (2020-02..2022-12, 35 months, purged leave-one-year-out): every price/text model has NEGATIVE
  out-of-fold IC (logit price -0.19, t_nw -3.9; +LM -0.18; +FinBERT -0.18) and loses 13-15 pts/yr to SPY;
  the no-skill equal-weight control beat SPY by +2.0 pts/yr. Text-only models: LM IC -0.04 (t -1.8),
  FinBERT -0.03 (t -1.2). Post-earnings drift features (gap, day-0, reaction) have ~zero IC in 2020-22.
* DEV Jev subset (2020-01..2021-06, half-year folds, 18 months): all sets negative IC; price+jev IC -0.13
  (t -1.95), -19.7 pts/yr vs SPY; Jev-only IC -0.10 (t -1.5).
* Expected TEST verdict: NO EDGE.

## Disclosures (things that happened before this file)
* Bug fixed in DEV: labels originally started at the entry-day OPEN, so they contained day0_x (a feature).
  That gave a spurious +0.10 IC. Labels now start at the next open.
* Prices originally started 2019-09, which silently dropped all events before 2020-09 (no 12-month history).
  Fixed with `s04c_prices_pre.py` (2018-08..2019-08 closes, spliced).
* Contamination: while diagnosing the DEV sign flips I printed univariate feature ICs by year for ALL years,
  including 2023-2026 (gap_x, day0_x, react_x, mom_12_1, mom_1m, vol60, lm_tone, lm_neg, fb_mean, fb_neg).
  No parameter, feature or setting was changed after that; the rule above is the one coded before it.
