# m05: insider cluster buying (with and without Jev footnote classification)

**Verdict: NO EDGE.** In the sealed TEST period (events filed 2016 to 2026q1) both frozen rules lose to both benchmarks, even before
any survivorship adjustment: A is 6.5% and A+B (Jev) is 7.9% CAGR after costs, against SPY at 15.2% and IWM at 10.6%. The event-level excess return vs IWM is
+0.2% per 126 days (t = 0.2). The DEV-period event alpha (+5.9% per 126d, t = 5.2) did not survive out of sample, and
at DEV costs it was already too small to beat the benchmarks. Jev adds nothing that simple keywords do not.

## Idea and rules (full detail in `PREREG.md`)
* An event is 3 or more distinct officers or directors with Form 4 open-market purchases (code P) within 30 days. It is dated by the **SEC filing
  date F**, and the position is **entered at the close of the first trading day after F**. There is a 182-day cooldown per issuer.
* Universe: yfinance price matched to the insiders' reported VWAP, price >= $2, ADV >= $100k, market cap <= $10B. Hold 126 trading
  days with equal weight at entry.
* **A** (Cohen-Malloy-Pomorski): at least 3 *opportunistic* (non-routine) insiders.
* **A+B**: A plus at least 3 insiders with a purchase that Jev does not classify as offering, private placement, plan or DRIP, or 10b5-1 (Jev agent m05
  read the anonymized footnotes and remarks: 28k unique states, 17.4M tokens, **$0.73**).
* Controls on the same dates: all events (`base`), a keyword and Loughran-McDonald dictionary version of B, and logistic regression with features A,
  A+Jev and A+dict.
* Costs (round trip): 300 bp if the price is under $5, otherwise 200 bp for micro caps, 80 bp for small caps and 30 bp for mid caps (the worse of the cap and ADV buckets). The realized
  average is about 1.3%.

## Results (H = 126d, CAGR after costs; `test_results/frozen_{dev,test}.csv`)

| | DEV 2006-15: A | DEV: A+B | TEST 2016-26: A | TEST: A+B | TEST base | TEST dict |
|---|---|---|---|---|---|---|
| Events with prices (independent bets) | 1216 | 1094 | 1677 | 1530 | 1900 | 1470 |
| CAGR, 1x costs | 7.5 | 7.5 | **6.5** | **7.9** | 6.2 | 7.8 |
| CAGR, 2x costs | 2.1 | 1.9 | 1.1 | 2.4 | 0.9 | 2.3 |
| CAGR, 0x costs | 13.2 | 13.4 | 12.1 | 13.7 | 11.8 | 13.6 |
| CAGR without the top 1% of events | 5.2 | 5.0 | 3.1 | 4.4 | 3.1 | 4.1 |
| Missing names at 0% | -2.4 | -2.5 | -1.0 | -0.6 | -1.0 | -0.7 |
| Missing names at -50% | -56.7 | -56.7 | -45.0 | -44.4 | -44.5 | -44.4 |
| Missing names at -100% | -81.1 | -81.1 | -69.7 | -69.1 | -69.1 | -69.1 |
| SPY / IWM, same window | 6.8 / 6.3 | 6.8 / 6.3 | 15.2 / 10.6 | 15.2 / 10.6 | 15.2 / 10.6 | 15.2 / 10.6 |
| Max drawdown | -58% | -59% | -49% | -49% | -49% | -50% |
| Mean / median event excess vs IWM | +5.9% / +1.5% | +6.3% / +1.9% | +0.2% / -2.6% | +0.3% / -2.9% | 0.0% / -2.4% | +0.2% / -3.1% |
| t-stat of the mean excess | 5.2 | 5.1 | 0.2 | 0.3 | 0.0 | 0.2 |

* Other horizons in DEV (`dev_results/rules.csv`, base / A): 21d -7.7 / -5.5, 63d 3.3 / 5.4, 252d 7.8 / 8.4. Short holds are killed by
  costs. The DEV variants were big buys, CEO/CFO, after a decline, all four combined, 4 or more insiders, 5 or more insiders, Jev indirect or range, and dict. All fell in the 4-9% range, with no
  stable winner across the two DEV halves (`rules_halves.csv`). In 2011-15 every variant was below SPY at 11.2%.
* ML (`dev_results/ml_*.csv`, `test_results/ml_*.csv`): the walk-forward DEV AUC was 0.503 (A), 0.505 (A+Jev) and 0.488 (A+dict). The frozen model's TEST
  AUC was 0.492 / 0.498 / 0.502, and its top-tercile TEST portfolios returned 4.1% / 4.6% / 6.0%. None of the three models has any skill.
* **The pre-registered Jev criterion failed.** A+B beat A by 1.4 points in TEST, but the plain keyword filter matched it (7.8%), and the Jev ML AUC
  (0.498) was below the dictionary model's (0.502). What the footnotes say (10b5-1 plans, offerings, DRIPs, indirect holdings) carries no usable
  return information beyond "3 or more insiders bought".

## Artifacts hunted and what was found
1. **Survivorship (the dominant problem).** yfinance has no delisted tickers, so only 23% of DEV events and 41% of TEST events can
   be priced. The priced subset is the firms that are still listed today, which is survivor-biased upward. That is the likely source of the
   DEV event alpha: it fell from +5.9% to +0.2% once TEST coverage (and so less selection) roughly doubled. The survivorship bounds are
   brutal because most events are missing. Even at a 0% return for missing names, both rules lose money in DEV and in TEST.
2. **Lookahead.** Positions are dated by the filing date, not the transaction date, and entered at the next day's close. Events whose cluster only
   became visible through late filings are skipped (the stale-cluster fix in `03b`). The routine and opportunistic split cannot be computed before 2009, because
   the data starts in 2006, so `n_opp == n_ins` in 2006-08.
3. **Costs.** 0x-cost CAGR is 12-14%, but real small-cap spreads take about 6 points a year at a 126d hold and almost everything at 21d.
4. **Tail dependence.** Dropping the top 1% of events costs 2-3 points of CAGR, and the median event underperforms IWM in TEST.

## Capacity and live trading
The capacity estimate is about $20M (10% of median ADV across about 75 concurrent positions), but it is moot because there is no edge. Trading this live would
need a daily EDGAR Form 4 feed (the acceptance timestamp), an issuer-to-ticker map including delisted names, and small-cap execution. A proper
re-test would also need a point-in-time price source with delisted names (CRSP or similar), which this container does not have.

## Files
* `01b_fetch_sec_fn.py`: SEC insider data sets 2006q1-2026q1, purchases plus footnotes (`01_fetch_sec.py`, `03_build_events.py`,
  and `04_fetch_prices.py` are superseded round-5 versions).
* `02_fetch_shares.py`: SEC shares outstanding. `03b_build_events.py`: events, purchases and members (`*_v2.parquet`).
* `04b_fetch_prices.py`: yfinance prices and splits. `05_backtest.py`: price matching, cost model and the portfolio simulator.
  `06_analyze.py`: universe, filters and survivorship bounds.
* `08_jev_score.py`: Jev plus dictionary features per purchase. `07_dev.py`: DEV rules and ML. `09_test.py`: the frozen DEV and TEST run (run once).
* Data (git-ignored): `data/round5/m05_insider_clusters/`. Logs: `dev_rules.log`, `dev_ml.log`, `frozen_{dev,test}.log`.
