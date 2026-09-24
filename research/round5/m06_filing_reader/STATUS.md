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

- s05 FinBERT (int8, first 16 narrative sentences) + LM scorer, resumable -> DATA/sc_partNNN.parquet
  (re-run `python s05_score.py texts_all.jsonl.gz sc` after the fetch finishes; it skips scored accs).
- s07 Jev features (questions frozen in jev_questions.py, 28 questions; text anonymised by textprep.py),
  3 I/O threads; cost ~5.7k tokens/call (~$0.00024/call, ~$3.4 for all ~14k events). Resumable via jev cache.
  Run `python s07_jev.py` (no arg = all dates) at the end to produce jev_features.parquet for all events.
- s04b: yfinance retry for 53 delisted tickers recovered nothing (Yahoo purged them). m01's close.pkl has
  empty columns for them. Survivorship handled by stress test (see README).

- Background drivers (02:40 UTC): run_s05_loop.sh (FinBERT, K=10 sentences, 64 tokens, int8; ~0.5 s/doc)
  and run_s07_loop.sh (Jev; fast jittered retry because the gateway returns frequent 503s; ~1.3 calls/s).
  Both re-run until s03 fetch ends; logs s05_loop.log / s07_loop.log in DATA. If killed, just relaunch them.

## Next
- s06_events.py (event table) -> s08_model.py dev -> PREREG.md -> s08_model.py test (ONCE) -> README.md
