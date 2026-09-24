# m06 filing reader: STATUS

## Done
- s01 universe: point-in-time S&P 500 intervals (data/.../sp500_pit_intervals.csv, READ-ONLY for others) + ticker_cik.csv
- s02: events_8k202.csv = 14,579 8-K Item 2.02 filings 2019-10..2026-09 made while the firm was an S&P 500 member (acceptance time UTC->ET in accept_et)
- s04: prices.parquet (yfinance adjusted OHLCV, 580 tickers + SPY; 53 delisted tickers missing). READ-ONLY for others.
- s05 (FinBERT + LM scorer) and s06 (event table) written, not yet run on full data.
- Round 5b restart: texts_dev.jsonl.gz was truncated (1,912 good records to 2020-07). Rescued into texts_all.jsonl.gz;
  s03 now self-rescues truncated output.

## Running
- s03 text fetch into data/.../texts_all.jsonl.gz, dev range then test range (log s03_all.log). Re-run the same
  command to resume: `python s03_fetch_text.py 2019-10-01 2022-12-31 texts_all.jsonl.gz` then `... 2023-01-01 2026-12-31 ...`

## Next
- Jev cost probe, question list (s07), FinBERT/LM scoring (s05), event table (s06), dev model + portfolio (s08).
