# m01 midcap momentum: STATUS

Last updated: 2026-09-24 (round 5b resume)

## Done (by earlier instances)
- Data: French 25 ME x Prior(12-2) + 10 Prior portfolios (monthly+daily), ME breakpoints,
  point-in-time S&P 400 membership 2012+ (membership_monthly.csv, changes.csv), close.pkl/volume.pkl
  (yfinance), defense_daily_x1/x2.csv. DO NOT overwrite those (m11 reads them).
- dev_portfolio.csv: French DEV 1927-1993 at 1x costs:
  ME2xPRIOR5 17.4% (DD -79%) / switch 14.9% (DD -55%); ME4xPRIOR5 16.9% / switch 15.0% (DD -38%);
  top decile 16.2% / 15.0%; market 9.9%.

## Done this session (5b)
- French DEV choice (french_dev_select.py -> french_dev_select.csv):
  ME3xP5 chosen because ME3 (NYSE 40-60th pct) is the size bucket that matches the S&P 400
  (ME2/3/4 DEV CAGRs 17.4/16.9/16.9% are within noise). ME3xP5 1x: 16.9% (+7.0 vs mkt, DD -75%);
  with switch 14.7% (+4.8, DD -45%). Switch costs -1.85 log-pts/yr (+8.9/yr in down months,
  -10.8/yr in up months); avoids 1929-32 (-72% -> -23%), 1937-38, 1973-74, but misses the
  1932-33 rebound (+55% -> 0%). Primary = no switch (max DEV excess), switch = pre-registered secondary.
- bench_close.pkl (NEW file): SPY IJH MDY XMMO XMHQ RSP. No S&P 400 equal-weight ETF available (EWMC gone).
- iShares historical holdings: NOT available (only latest-holdings.csv).
- Membership quality concern: Wikipedia change table has only 17/25/43/21 changes in 2012-2015 vs
  ~50/yr later -> reconstruction likely incomplete in early DEV (future-addition look-ahead risk).
  Fix in progress: wiki_revisions.py builds an independent strictly-PIT membership from the page's
  own revision history -> DATA/membership_wikirev.csv (+ wiki_rev/ cache). Rate-limited (429), slow.

## In progress
- wiki_revisions.py FINISHED: DATA/membership_wikirev.csv (177 month-ends 2011-2025, ~400 names).
- PREREG.md WRITTEN (French: primary ME3xP5 no switch, secondary ME3xP5+switch, 15bp x 0.80 TO/month,
  bench = French Mkt).
- FRENCH TEST DONE (run once, french_test.py -> french_test.csv, french_test_yearly.csv), 1994-01..2026-07:
  ME3xP5 1x 11.4% vs mkt 10.9% (+0.5), 2x 9.8% (-1.1); DD -53% (mkt -50%); beat mkt 17/33 yrs.
  ME3xP5+switch 1x 11.2% (+0.3), 2x 9.8% (-1.1), DD -39%. vs ME3 size quintile 10.5%.
  => Portfolio-level verdict NO EDGE (prereg criterion: >+2 at 1x and >0 at 2x not met).
- STOCK DEV DONE (stock_dev.py rev chg -> stock_dev_summary.csv, stock_dev.log, books/), 2012-01..2018-12,
  1x costs vs SPY 12.3%: top5 -4.5..-10.0 pts even in survivor-biased 'drop'; top10 -3.4..-4.2; top80 ~0.
  Missing-price hole 36-45% of members. Concentration monotonically hurts -> no stock TEST pre-registered
  (DEV already fails; stock TEST 2019+ deliberately NOT run).
- README.md WRITTEN: final verdict NO EDGE. m01 COMPLETE. (Optional, not done: stock TEST 2019+.)

## Next steps
1. Pick final French config on DEV only; write PREREG.md; run French TEST 1994-2026 once.
2. Stock level (S&P 400 PIT, DEV 2012-2018 / TEST 2019+): top5/top10, survivorship bounds, costs 1x/2x.
3. README.md report + verdict.
