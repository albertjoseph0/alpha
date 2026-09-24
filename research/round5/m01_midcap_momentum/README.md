# m01 mid-cap momentum: verdict **NO EDGE**

**Idea.** Buy mid-cap winners: the top quintile of 12-2 momentum inside the NYSE 40th-60th size
percentile (the S&P 400 range). Optionally add the deep_trend_switch market-trend switch. Tested at two
levels: century-long French portfolios, and concentrated top-5/top-10 stock books on point-in-time
S&P 400 membership.

## 1. Portfolio level (Ken French 25 ME x Prior 12-2, value-weighted), the main test
Pre-registered in `PREREG.md` before TEST. Primary strategy: ME3xPRIOR5, always invested. Secondary:
the same book with the trend switch into T-bills. Costs: turnover 0.80 per month at 15 bp one-way
(1.44%/yr); 2x costs = 30 bp. Benchmark: French value-weighted market. Script: `french_test.py`,
output in `french_test.csv` and `french_test_yearly.csv`. TEST was run once.

| Period | Strategy | CAGR 1x | CAGR 2x | Market | Excess 1x | Excess 2x | Max DD (mkt) | Years beating market |
|---|---|---|---|---|---|---|---|---|
| DEV 1927-93 | ME3xP5 | 16.9% | 15.2% | 9.9% | **+7.0** | +5.3 | -75% (-84%) | 50/67 |
| DEV 1927-93 | ME3xP5 + switch | 14.7% | 13.4% | 9.9% | +4.8 | +3.5 | -45% | 43/67 |
| **TEST 1994-2026.07** | **ME3xP5** | **11.4%** | **9.8%** | **10.9%** | **+0.5** | **-1.1** | -53% (-50%) | 17/33 |
| TEST 1994-2026.07 | ME3xP5 + switch | 11.2% | 9.8% | 10.9% | +0.3 | -1.1 | -39% | 13/33 |

* The mid-cap size quintile itself earned 10.5% in TEST, so momentum added about +0.9 pts/yr over the
  plain mid-cap bucket before costs and about 0 after them.
* TEST subperiods (1x costs, no switch vs market): 1994-2001 15.8% vs 13.0%; 2002-09 3.5% vs 2.6%;
  2010-17 13.0% vs 14.2%; 2018-26 13.4% vs 14.1%. What edge there was ended around 2009.
* Yearly excess (1x costs) ranged from +31.5 (1999) to -21.9 (2009). It was negative in 2009
  (momentum crash) and in 7 of the 9 years from 2017 to 2025. The full series is in `french_test_yearly.csv`.
* The switch cut the TEST max drawdown from -53% to -39% (2008: -6% vs -38%). It gave all of that back
  in the rebounds (2009, 2019, 2020), for a net of -0.2 pts/yr. That matches DEV, where the switch
  also cost about 2 pts/yr of CAGR.
* The pre-registered criterion (above +2 at 1x costs and above 0 at 2x) is not met, so the verdict is **NO EDGE**.
  The DEV premium of +7 pts/yr shrank to +0.5 out of sample. That fits the known post-1993
  (post-Jegadeesh-Titman publication) decay of US momentum.

## 2. Stock level: concentrated S&P 400 top-5 and top-10, DEV 2012-2018 only
`stock_bt.py` and `stock_dev.py`, output in `stock_dev_summary.csv` and `books/`.
* Rank on 12-1 momentum at the last close of each month and trade at the next day's close (1-day lag).
  Prices come from yfinance. Membership is point-in-time from two independent sources: `chg` walks the
  current list backwards through Wikipedia's change table; `rev` uses the constituents table in
  Wikipedia revisions saved on or before each month end (`wiki_revisions.py`).
  That second source was built because the change table is visibly incomplete for 2012-15.
* Survivorship: 36% (`chg`) to 45% (`rev`) of point-in-time members have no usable yfinance
  price, because they were delisted, acquired or their tickers were reused. Results are bounded with
  several scenarios. `drop` ignores them, which biases returns upward. `neutral` gives those slots the
  universe return. `x50` and `x100` give -50% or -100% to missing names that leave the index. `m50` and `m100` are literal extreme bounds.
* DEV, 1x costs (15 bp), versus SPY at 12.3%:

| Book | `drop` (upward-biased) | `neutral` | `x50` | `x100` |
|---|---|---|---|---|
| top 5 (`rev` / `chg`) | 2.3% / 7.9% | 5.3% / 8.0% | 0.2% / 4.7% | -4.9% / 1.5% |
| top 10 (`rev` / `chg`) | 8.1% / 9.0% | 8.6% / 8.7% | 3.4% / 5.4% | -1.8% / 2.2% |

  Excess return rises steadily as the book widens: top5 -4.5 to -10.0, top10 -3.4 to -4.2, top20 -2.7,
  top40 -0.6, top80 0.0 (all `drop`, 1x costs). Max DD for top 5 was -34% to -35%, versus -19% for the equal-weight universe.
  The trend switch did not help: its effect ranged from -1.5 to +0.5 pts.
* Even the survivor-biased best case loses to SPY in DEV, so there was nothing to pre-register.
  **The stock-level TEST (2019+) was deliberately not run.** It would only have been a second look at
  a rule that had already failed.

## Required report items
* **Independent bets:** French TEST covers 391 months and 33 calendar years. ME3xP5 holds a median of
  111 names (65-321), with turnover of about 0.8 per month. The stock DEV covers 84 monthly rebalances
  of 5 or 10 names.
* **Capacity:** not binding. ME3xP5 names averaged about $5.2B market cap in 2026, so a value-weighted
  book could absorb billions. There is no edge to capacity-limit.
* **Main artifacts hunted:**
  1. Look-ahead in the momentum timing. French PRIOR is formed on returns t-12..t-2, and the stock
     books use a 1-day lag.
  2. Survivorship. French/CRSP data includes delisting returns. The stock books have an explicit
     36-45% hole, bounded as described above.
  3. Look-ahead in the membership reconstruction. Two independent point-in-time sources were built.
  4. Dead or reused yfinance tickers, filtered out by zero-volume detection.
  5. Choosing a size bucket on DEV. ME2, ME3 and ME4 were within noise, and ME3 was picked because it can be traded.
  The main finding is not an artifact. It is plain decay: the DEV premium does not survive into 1994-2026.
* **Trading it live:** the closest real product is an S&P MidCap 400 momentum ETF (for example XMMO)
  or a monthly-rebalanced top-quintile mid-cap book. On this evidence, expect about market returns
  with deeper drawdowns and multi-year stretches of underperformance. Not recommended as a moonshot.
