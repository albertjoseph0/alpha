# m01 midcap momentum: STATUS

Last updated: 2026-09-24 (round 5b resume)

## Done (by earlier instances)
- Data: French 25 ME x Prior(12-2) + 10 Prior portfolios (monthly+daily), ME breakpoints,
  point-in-time S&P 400 membership 2012+ (membership_monthly.csv, changes.csv), close.pkl/volume.pkl
  (yfinance), defense_daily_x1/x2.csv. DO NOT overwrite those (m11 reads them).
- dev_portfolio.csv: French DEV 1927-1993 at 1x costs:
  ME2xPRIOR5 17.4% (DD -79%) / switch 14.9% (DD -55%); ME4xPRIOR5 16.9% / switch 15.0% (DD -38%);
  top decile 16.2% / 15.0%; market 9.9%.

## In progress
- Resumed: reading scripts, checking data.

## Next steps
1. Pick final French config on DEV only; write PREREG.md; run French TEST 1994-2026 once.
2. Stock level (S&P 400 PIT, DEV 2012-2018 / TEST 2019+): top5/top10, survivorship bounds, costs 1x/2x.
3. README.md report + verdict.
