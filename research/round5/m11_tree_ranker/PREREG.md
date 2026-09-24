# PREREG: m11 gradient-boosted tree ranker (written 2026-09-24, BEFORE any TEST run)

## What DEV showed (2014-01..2019-12 holding months; 2012-13 = warm-up / first training window)
No config had a DEV rank IC distinguishable from zero (all |IC| <= 0.007, |t| <= 0.4). Every model
top-25 book trailed SPY (12.2%/yr) and the EW universe (11.1%). The selection below is therefore selection
on noise, which I say here in advance. I am running TEST anyway, because the brief requires a sealed
out-of-sample check and because DEV includes the heaviest survivorship hole (15-31% of members lack data).

## Frozen rule
- Universe at each month-end formation f: point-in-time S&P 500 (m11 rebuild from Wikipedia changes) U
  S&P 400 (m01 rebuild), with a price at f and >= 245 valid closes in the prior 253 trading days.
- Features (18, rank-normalised cross-sectionally each month to [-0.5, 0.5]): mom12_1, mom6_1, rev1,
  resmom (12-1 residual vs SPY + best-matching sector SPDR, daily 252d), hi52, vol1, vol12, maxret1, beta,
  ivol, secmom, size_dv (log median $ volume 252d, size proxy), dv_trend, amihud, logprice, short_ratio
  (FINRA short vol / total vol, last 10 trading days of the month), short_chg (vs 3 months earlier), is500.
  Insider-cluster flag NOT used (m05 events cover only 2006-07).
- Label: cross-sectional percentile of the next holding-period return.
- Model: sklearn HistGradientBoostingRegressor, lr 0.05, max_leaf_nodes 31, max_iter 300,
  min_samples_leaf 500, l2 1.0, no early stopping, random_state 0 (config `hgb_l31_i300`,
  chosen as the best DEV mean rank IC among the 4 HGB configs, as the rule fixed before the DEV run said).
- Walk-forward: refit each December formation on all rows whose label window has closed (t1 <= f),
  expanding window from 2011-12.
- Portfolio: top K=25 by score, equal weight, rebalanced monthly. Features at the close of the last
  trading day of month m; trade at the close of the next trading day; hold to the close of the first
  trading day of month m+2 (1-day lag).
- Costs per side: 5 bp for S&P 500 names, 12 bp for S&P 400 names; also reported at 2x.
- Survivorship: members without yfinance data are the hole; scenarios drop / neutral / x50 / x100 (the no-data
  members that leave the index in the holding month lose 50% or 100%, the rest earn the EW universe return,
  with random-selection weight q = n_nodata/n_members). Held names whose price series ends inside the
  holding window: exit at the last price (base), plus -50% and -100% stress.
- Secondary variant: the same book with the SPY trend switch (126/168/210/252-day ensemble,
  read at the formation close) into m01's deep_trend_switch defensive ETF sleeve.

## Test
TEST = holding months 2020-01..2026-08 (formations 2019-12-31..2026-07-31), run ONCE with
`s05_model.py test hgb_l31_i300 rf_baseline ridge_linear`, then `s06_report.py test hgb_l31_i300`.
RF and ridge are reported only as baselines; the primary is hgb_l31_i300.
Controls on identical dates: 12-1 momentum top-25 (same universe, costs), EW eligible universe, SPY.

## Benchmark and success criterion (primary = model top-25, no switch, 1x cost, missing=drop)
- MOONSHOT CANDIDATE: TEST CAGR >= SPY CAGR + 20 pts, and still >= SPY + 20 under missing=x50.
- REAL BUT SMALLER: TEST CAGR > SPY and > the 12-1 momentum control and > the EW universe, and model
  mean rank IC t-stat >= 2.
- Otherwise NO EDGE.
