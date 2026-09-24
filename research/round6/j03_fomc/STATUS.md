# j03_fomc STATUS

Idea: Jev reads FOMC statements (diff vs previous) and minutes; a tiny ridge model tilts SPY/QQQ/IWM/TLT/IEF/SHY/GLD.
DEV = events 1994-2012, TEST = 2013-01-01 .. 2026-09-23 (sealed until PREREG.md exists).

## Done
- [x] fetch_fed.py: 507 docs (247 statements, 260 minutes) in data/round6/j03_fomc/docs, meetings.csv.
      Missing: 2008-06 minutes (no HTML on the site).
- [x] fetch_prices.py: prices.parquet (ETF OHLC via yfinance + pre-inception proxies; FRED yields). proxy_check.csv
- [x] features.py -> docs.parquet: anonymised text (textprep.py), (a) market-reaction and (b) dictionary features.
      DEV: 133 S + 150 M events; TEST: 114 S + 110 M.
- [ ] jev_features.py (question set v1) -> jev_scores.parquet. First run died on a gateway 503 at doc ~316/507 ($0.037 spent, 325 calls,
      all cached). Restarted (resume session) -> log data/round6/j03_fomc/jev_features2.log; cached docs are free.
- [ ] leak_probe.py and jev_features.py (TEST docs) restarted in background (logs leak_probe.log, jev_features3.log).
      Gateway is flaky (503s/hangs; ~2 calls/min). Both resume from cache when rerun. Spend so far ~$0.045 of $1.
- [x] jev_scores.parquet for the 283 DEV docs built from cache (jf.main(283)); full run (TEST docs) still going in background.
- [x] dev.py -> dev_results.txt/csv. Walk-forward OOS 2000-02..2012-12, 216 events, SE(IC)=0.068.
      OOS IC (eq/dur, alpha=1): a_notext 0.087/0.051, b_dict 0.012/-0.027, c_jev -0.076/-0.034.
      CAGR next-open 3bp: a 8.40, b 5.38, c 1.53; neutral 5.69; SPY 1.93; 60/40 4.70.
      Paired c-b: -4.1 pts/yr, t=-2.29. Jev features' univariate corr with next-period returns all |r|<0.08.
      => DEV says Jev adds nothing (negative). Question set v1 only; no iteration (budget + multiple testing).
- [x] PREREG.md written (primary c_jev frozen, next-open, 3bp; test.py edited: next-open primary, neutral start)
- [ ] test.py run once
- [ ] README.md

## Notes
- Primary execution must be NEXT-OPEN (features use the event-day close; trading at that close is same-bar).

## Next step
Write PREREG.md (primary = c_jev frozen on DEV, next-open, 3bp; success = c beats b and SPY+20). Then test.py once, then README.md.
(old) When jev_features.py finishes (jev_scores.parquet exists): run leak_probe.py and dev.py. If it dies again, just rerun it.
