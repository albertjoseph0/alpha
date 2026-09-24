# o02 Beige Book sector rotation + Jev: STATUS (written by the orchestrator at hand-over)

## Done
- s01_fetch.py → data/orch/o02_beige_book/editions.jsonl.gz: 236 editions, 1996-10 to 2026-08, with release dates.
  Dates come from the URL (1996–2010) or the PDF file names; 14 editions fell back conservatively to the month
  end. Texts are full reports (2011–2023, truncated at 60k chars), summary pages (1996–2010), or summary pages
  with district highlights (2024+).
- s02_jev.py: cuts each edition to its national summary (before the district sections) and strips dates, then
  asks Jev the direction of change for 12 sectors (choice → expected value in [−2, 2], NaN if not mentioned),
  plus uncertainty and outlook, plus a leakage probe ("did stocks rise over the next 6 months?"). The first run
  hit a transient Jev 503; jev.py now retries 10×. Re-run it; cached answers are reused.

## Caveat
The national summary has sector sections before 2017 only. From 2017 it is shorter prose, so more
"not_mentioned" answers are expected. Fill those from "overall", and report the share of missing values
by era.

## Next steps
1. Run s02_jev.py (Jev budget "o02" = $1). Check the score distributions by era and the leakage-probe AUC
   against realized SPY 6-month returns.
2. Map sectors to Select Sector SPDRs (in data/etf_universe_daily.csv from 1998-12):
   - consumer → XLY
   - manufacturing + transport → XLI
   - manufacturing + construction → XLB
   - banking → XLF
   - energy → XLE
   - services → XLK
   - defensives (XLP, XLV, XLU) when overall is weakening
3. Write a harness Strategy (rebalance on the day after each release; the harness adds a 1-day lag) and run DEV
   `etf_dev` (2000–2015). Compare with (a) sector 12-1 momentum top 3 on the same dates, the equal-weight 9
   sectors, and SPY; and (b) a dictionary tone baseline on sector sentences. Pre-register the rule in PREREG.md,
   then run TEST `etf_holdout` once (ALPHA_HOLDOUT=1).
4. README.md with the verdict.
