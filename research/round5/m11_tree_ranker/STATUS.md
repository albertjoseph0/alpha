# m11 tree ranker: STATUS

## Done
- s01_universe.py: S&P 500 PIT monthly membership 2011-12..2026-09 rebuilt from m06's Wikipedia HTML
  (read-only) -> DATA/sp500_membership_monthly.csv (5 minor inconsistencies logged in sp500_issues.csv).
- s02_prices.py: yfinance close+volume for S&P 500 names missing from m01's panel + 9 sector ETFs;
  merged with m01's S&P 400 panel -> DATA/close.pkl, volume.pkl (1167 tickers, 2010-06..2026-09-23).
  148 historical S&P 500 tickers have no yfinance data (delisted). Survivorship hole (no-data members /
  union members): 35% in 2011-12, 31% 2013-12, 20% 2017-12, 13% 2019-12, 8% 2022-12, 2% 2025-12.
- s03_finra.py: FINRA short volume (facility files FNSQ+FNYX+FNQC+FORF, last 10 trading days/month)
  -> DATA/finra/YYYY-MM.csv. (Running in background; resumable.)
- s04_features.py: panel (18 features, labels, months.csv incl. survivorship counts) -> DATA/panel.parquet.
- s05_model.py: walk-forward HGB/RF/ridge + controls; logs every config run to configs_log.csv.
  NOTE: import common BEFORE sklearn (OMP threads=1), otherwise runs crawl under load.
- Debug DEV run (hgb_l7_i100, FINRA incomplete): IC -0.006 (t -0.39), 8.4% CAGR vs SPY 12.2%,
  mom12_1 top25 8.4%, EW universe 11.1% (2014-01..2019-12). Logged, not used for selection.
- m05 insider events only cover 2006-2007 at the moment -> insider feature skipped (not cheaply available).

- FINRA done (183 months). Panel rebuilt with full short features.
- DEV selection run (all 6 configs, configs_log.csv): all IC ~0 (|t|<0.4); best HGB IC = hgb_l31_i300
  (IC 0.0034, t 0.24) -> frozen. DEV: model 8.2%/yr vs SPY 12.2%, EW 11.1%, mom 8.4%; +switch 4.4%.
  report_dev_hgb_l31_i300.md has everything.
- PREREG.md written (2026-09-24) BEFORE any test run.

## Next step
- run TEST once: `s05_model.py test hgb_l31_i300 rf_baseline ridge_linear` then `s06_report.py test hgb_l31_i300`;
  then write README.md.
