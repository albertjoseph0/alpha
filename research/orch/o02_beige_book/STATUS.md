# o02 Beige Book sector rotation + Jev: STATUS

Owner: research agent o02 (took over from the orchestrator 2026-09-24). Jev agent id "o02", budget $1.

## Done
- s01_fetch.py → data/orch/o02_beige_book/editions.jsonl.gz (orchestrator; 236 editions). Kept unchanged.
- **s01b_dates.py → editions_fixed.jsonl.gz + release_dates_audit.csv (239 editions).** The s01 dates were wrong in
  a lookahead direction: 2011–2012 dates parsed from in-text dates (e.g. 2011-01-03 vs the true 2011-01-12), and 2024+
  month-end fallbacks were BEFORE the true release (URL month = report month; beigebook202402 came out 2024-03-06).
  The fix uses the URL date, the PDF next to the link on the year page, the edition's own PDF, and "Last Update"
  (2017+), and takes the latest date. 21 dates were changed or added: 3 editions s01 missed (2011-03-02, 2015-03-04,
  2023-05-31); 2003-09-10 is a 404 and stays missing. All are Wednesdays except 2006-10-12 (Thu, correct), plus
  2019-12-03 and 2022-07-19, which are conservative (the "Last Update" is 6 days after the PDF date).
- s02_jev.py now reads editions_fixed, uses 4 threads, and its probe call adds a sector probe (the best sector over
  the next 6 months, 9-way choice) next to the market probe.

## Running / next
1. Run s02_jev.py (Jev spend so far $0.011 from the orchestrator's first 58 calls). Check the score distributions
   by era, the missing share, and the leakage probe AUC.
2. s03_dict.py: dictionary tone baseline on sector sentences (keyword sentence selection + up/down direction words).
3. s04_signals.py: per-release sector scores for (a) 12-1 momentum, (b) dictionary, (c) Jev → IC vs next-period
   ETF returns on DEV; strategy.py (harness) top-3 rule; run etf_dev variants at 1× and 2× costs.
4. PREREG.md, then etf_holdout once (ALPHA_HOLDOUT=1). README.md with the verdict.

## Mapping (fixed before any results, from the orchestrator's hand-over)
consumer→XLY; mean(manufacturing, transport)→XLI; mean(manufacturing, construction=mean(resi_re, cre))→XLB;
banking→XLF; energy→XLE; services→XLK; XLP/XLV/XLU score = −overall. NaN sector → overall.
