# m05 insider clusters: STATUS (Round 5b resume)

## State found at resume (2026-09-24)
* Scripts 01-06 existed; 01 had fetched SEC form345 2006q1-2023q4 compact files; old `events.parquet`
  only covers 2006-01..2007-09 (built mid-fetch; left untouched). No prices, results or PREREG existed.

## Done
1. `01b_fetch_sec_fn.py`: all quarters 2006q1-2026q1 (latest SEC set; 2026q2 = 404), new
   `quarters/{yq}_pfn.parquet` (code-P rows + footnote text + remarks + AFF10B5ONE). No errors. Zips deleted.
2. `03b_build_events.py` -> `events_v2.parquet` (16,301 events 2006-2026q1), `purchases_v2.parquet`
   (561,715 clean officer/director purchases), `event_members_v2.parquet` (112,662 cluster purchases).
   Fix vs 03: skip "stale" clusters where no filing on F is in the window.
3. 05_backtest.py now reads `*_v2` files (TAG) and uses a 20-day lag on SEC shares outstanding;
   06_analyze.py caches `prepared_v2.pkl`.

4. Prices DONE (1,978 tickers in px/, 5,096 symbols missing; 2 passes). `prepared_v2.pkl` built:
   of 16,301 events only 5,051 status ok (9,913 no_yf_data = mostly delisted -> survivorship bounds matter).
5. Jev scoring DONE: `jev_purchase_v2.parquet` (112,662 cluster purchases; 3,388 with text unscored ->
   Jev probs 0 = treated as 'not stated'); spend $0.73 of $5. Note: lm_unc column is all 0 (LM
   uncertainty list did not match footnote text) - harmless, dictionary baseline uses neg/pos + keywords.

## Running / next (resume 2026-09-24 11:25)
* Then: `07_dev.py prep` (price matching, cache), `07_dev.py rules`, `07_dev.py ml` -> dev_results/.
* Then PREREG.md (A and A+B), 09_test.py once, README.md.

### 11:40 DEV rules (07_dev.py rules -> dev_results/rules.csv, log data/.../dev_rules.log)
* DEV 2006-2015, priced universe only 24% of events (76% no yfinance data = delisted).
* H=126: base 6.6% CAGR, opportunistic (A) 7.5%, A+Jev clean (B) 7.5%, dict 7.6%; SPY 6.8%, IWM 6.3%.
  2x costs ~2%. Missing names at -50%: ~-57%; at -100%: ~-81%. Event mean excess vs IWM +5.9%/126d (t=5.2)
  but median +1.5%: skewed, mostly eaten by costs (0x-cost CAGR 13%). => clearly no moonshot.
* 09_test.py written (frozen A/A+B/base/dict at H=126 + ML frozen). Next: 07_dev.py ml, PREREG.md, then
  `09_test.py dev` and `09_test.py test` ONCE, README.md.

### PREREG.md written (frozen A = opportunistic n_opp>=3, A+B = `B:jev_clean>=3 & opp`, H=126).
* Running in background: `07_dev.py ml` (log dev_ml.log) -> `09_test.py dev` (frozen_dev.log) -> `09_test.py test`
  (frozen_test.log, ends with ALLDONE; results in test_results/). TEST IS RUN ONCE: if frozen_test.log already
  has results, do NOT re-run; just write README.md from test_results/*.csv.
* DEV ML (walk-forward 2009-15, dev_results/ml_*.csv): AUC A 0.503, A+Jev 0.505, A+dict 0.488 (no skill);
  top-tercile portfolios A 16.8%, A+Jev 15.0%, A+dict 19.6%, all 13.7% vs SPY 13.4%, IWM 12.9% (priced names only).

## FINAL (2026-09-24): TEST RUN DONE ONCE. Do not re-run 09_test.py test. README.md written. VERDICT: NO EDGE.
* TEST 2016-26, H=126, 1x costs: A 6.5% (2x 1.1%), A+B 7.9% (2x 2.4%), base 6.2%, dict 7.8%; SPY 15.2%, IWM 10.6%.
  Event excess vs IWM +0.2%/126d (t=0.2). Missing at 0/-50/-100%: about -1 / -45 / -70%. Excluding the top 1%: 3.1 / 4.4%.
* Jev criterion failed: the keyword filter matches A+B, and TEST AUC is Jev 0.498 vs dict 0.502 vs A 0.492. Jev spend $0.73.
