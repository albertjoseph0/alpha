# j03_fomc STATUS

Idea: Jev reads FOMC statements (diff vs previous) and minutes; a tiny ridge model tilts SPY/QQQ/IWM/TLT/IEF/SHY/GLD.
DEV = events 1994-2012, TEST = 2013-01-01 .. 2026-09-23 (sealed until PREREG.md exists).

## Done
- [x] fetch_fed.py: 507 docs (247 statements, 260 minutes) in data/round6/j03_fomc/docs, meetings.csv.
      Missing: 2008-06 minutes (no HTML on the site).
- [x] fetch_prices.py: prices.parquet (ETF OHLC via yfinance + pre-inception proxies; FRED yields). proxy_check.csv
- [x] features.py -> docs.parquet: anonymised text (textprep.py), (a) market-reaction and (b) dictionary features.
      DEV: 133 S + 150 M events; TEST: 114 S + 110 M.
- [ ] jev_features.py (question set v1) -> jev_scores.parquet   (running)
- [ ] leak_probe.py
- [ ] dev.py (walk-forward OOS 2000-2012 inside DEV)
- [ ] PREREG.md
- [ ] test.py run once
- [ ] README.md

## Next step
When jev_features.py finishes: run leak_probe.py and dev.py.
