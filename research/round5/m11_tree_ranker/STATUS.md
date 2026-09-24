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

## Next step
- when s03 finishes (log DATA/s03.log reaches 2026-08): rerun s04, then `s05_model.py dev` (all 6 configs),
  pick best by DEV mean rank IC, write PREREG.md, then `s05_model.py test <config>` once; s06_report.py.
