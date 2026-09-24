# j09 dividends: STATUS

Idea: post-dividend-initiation/increase drift (Michaely, Thaler & Womack 1995); hypothesis: announcements stating a
durable policy commitment drift more than one-time/special dividends. Jev reads the 8-K press release.
DEV = 2013-2019, TEST = 2020+ (sealed until PREREG.md). Jev agent "j09", budget $1.50.
Code: research/round7/j09_dividends/ ; data: data/round7/j09_dividends/ (DATA).

## Done
- common.py (paths, periods, membership(), close()).
- s01_universe.py -> DATA/universe_monthly.parquet, DATA/ticker_cik.csv. S&P 500 (m11) + S&P 400 (m01) PIT monthly,
  1522 tickers, 1183 with CIK, 1153 with prices. Member-month share with CIK & price: 72% (2013), 86% (2019), 88% (2020),
  97% (2025). The rest (delisted names) is the survivorship hole.

## Running
- s02_xbrl.py (companyfacts.zip -> DATA/dps_facts.parquet), log DATA/s02.log.
- s03_fts.py (EDGAR full-text search 8-K phrases 2012-2026, all filers) -> DATA/fts_hits.parquet, log DATA/s03.log.
  Rerunning is cheap: every efts page is cached by sec.get.

## Next
- s04_events.py: filter FTS hits to PIT universe CIKs, dedupe per filing, quarterly DPS from XBRL, match -> events.
- s05_fetch.py: fetch the matched documents' text (resumable), s06 opens via yfinance, then features, Jev, DEV.
