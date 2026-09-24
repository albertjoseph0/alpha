# m01 PREREG: French portfolio-level mid-cap momentum (written before any TEST data was used)

Written 2026-09-24. Everything below was chosen using DEV 1927-01..1993-12 only
(dev_portfolio.py, french_dev_select.py). The TEST period 1994-01..2026-07 (last month in the
French file) is run once by french_test.py and reported exactly as it comes out.

## Frozen rule
* Data: Ken French "25 Portfolios Formed on Size and Prior (12-2) Return", value-weighted monthly.
* **Primary strategy: ME3 x PRIOR5** (NYSE size quintile 3, i.e. 40th-60th pct, the size bucket that
  matches the S&P 400; top NYSE quintile of 12-2 momentum). Long only, held all the time.
  Chosen on DEV because ME2/ME3/ME4 x PRIOR5 DEV CAGRs (17.4/16.9/16.9%) are within noise, and ME3
  is the bucket that can actually be traded through the S&P 400. No switch = the max DEV excess.
* **Secondary strategy (pre-registered, reported alongside): ME3 x PRIOR5 with the trend switch.**
  Exposure u = fraction of 4 market trend signals (126/168/210/252-day total return of the French
  market > 0) measured at the close of the penultimate trading day of month t-1, applied to month t;
  the rest in T-bills (French RF). DEV: 14.7%, max DD -45%.
* Signal timing: French PRIOR uses returns t-12..t-2, formed at the end of t-1, so there is at least
  a one-month skip before the holding month.

## Frozen costs
* Turnover of the winner book: 0.80 (sum |dw|) per month; one-way cost 15 bp per $ traded
  -> 1.44%/yr drag at 1x. Switch changes cost (15 + 1) bp per unit of |du|.
* 2x costs: 30 bp one-way (2.9%/yr drag). Both reported.

## Benchmark and success criterion
* Primary benchmark: French value-weighted market (Mkt-RF + RF), total return, no costs.
* Secondary, diagnostic only: the ME3 size quintile itself (value-weighted across its 5 prior
  buckets using number of firms x average size), to separate "mid-cap" from "momentum".
* Verdict on TEST CAGR excess over the market, primary strategy, 1x costs:
  * `MOONSHOT CANDIDATE`: >= +20.0 pts/yr.
  * `REAL BUT SMALLER`: > +2.0 pts/yr at 1x AND > 0 at 2x costs.
  * `NO EDGE`: otherwise.
* Also reported: max drawdown, yearly excess, share of years beating the market, 2x-cost numbers,
  and the secondary (switched) strategy on the same basis.

## Caveats known in advance
* French portfolios are not directly investable: they are CRSP-based (no survivorship bias, delisting
  returns included) but assume trades at month-end closes with the cost assumption above.
* One ME3xP5 portfolio holds ~100-300 names; a real mid-cap implementation would hold fewer.
