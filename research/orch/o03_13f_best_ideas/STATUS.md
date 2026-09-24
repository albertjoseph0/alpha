# o03 13F best-ideas cloning: STATUS

## Done
- s01_fetch13f.py: downloads each SEC 13F data set ZIP (list from
  https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets), reduces it to
  data/orch/o03_13f_best_ideas/proc/<tag>_{filings,agg,pos}.parquet, and deletes the ZIP. Units repair: consensus
  13F price per CUSIP; filings off by ~1000x are rescaled (77 of 4038 in 2014q1), rows still >4x off are flagged `bad`.
  Tested on 2014q1 (13F total at 2013Q4 = $18.3T; the top names are AAPL, GOOG, XOM, MSFT...).
- Background run started for 2014q1 through 01jun2026-31aug2026 (log data/orch/o03_13f_best_ideas/s01.log). It is
  restartable: it skips tags whose _pos.parquet exists.

## Next steps
1. s02: qualifying managers (10-100 equity positions, >= $100M, not bank/broker/index by name), best ideas by
   portfolio weight minus 13F-aggregate market weight, consensus top-N names; the most-held baseline.
2. CUSIP -> ticker (OpenFIGI is reachable, 25 req/min without a key, 10 CUSIPs per request), then yfinance prices.
3. DEV backtest (portfolios formed 2014-2019), then PREREG.md, then TEST once.
