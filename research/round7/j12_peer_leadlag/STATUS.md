# j12 peer lead-lag (text-based competitor peers + Jev): STATUS

Agent j12, Jev budget $1.50 (`agent="j12"`). Folder research/round7/j12_peer_leadlag/, data data/round7/j12_peer_leadlag/.
DEV = 2013-01..2019-12, TEST = 2020-01..2026-08 (sealed; PREREG.md must be written before any TEST run).

## Design decisions (fixed so far)
- Universe: PIT S&P 500 (m11) UNION S&P 400 (m01) monthly members, restricted to tickers with prices in m11 close.pkl
  (survivorship hole: 31% of members unpriced in 2013, 13% in 2019, 2% in 2025 -> quantify vs RSP).
- Text formations every 3 years (end of April 2012, 2015, 2018 | 2021, 2024), not yearly: the shared SEC limiter gives
  ~1,000 requests/h per agent (15 concurrent fetchers on 4 req/s), a yearly refresh = ~10,500 10-Ks (~10 h).
  Peer sets are rebuilt at each text formation; targets = priced members at the month that have a peer set
  (recent index entrants wait until the next text formation). Deviation from "refreshed yearly" -> flag in README.
- Signal month m: peer mean return over month m minus own return; top quintile, equal weight; entry at close of the
  first trading day after month-end (1-day lag), hold one month.
- Costs one-way 10 bp (S&P 500 names) / 20 bp (S&P 400 names); 2x = 20/40 bp.
- Jev billing test: state billed once, +40-70 tokens per extra question -> ~3k tokens per firm-doc.

## Done
- s01_universe.py -> DATA/universe_monthly.parquet (month_end, ticker, idx, cik, has_px); 1,554 CIKs.
- extract.py: html_to_text (copied from j01) + Item 1 (longest span) + competition passages; checked on 6 docs.

## Running
- run_fetch.sh (background): s02_submissions.py (1,013 needed CIKs -> DATA/subm_rows.csv, firms.jsonl, marker s02_done)
  then s03_docs.py for F2012,F2015,F2018 (DEV) then F2021,F2024 -> DATA/docs/F<y>.jsonl.gz. Logs s02.log, s03.log.
  Resumable: just re-run run_fetch.sh.

## Next
- s04_returns.py (monthly panel with 1-day lag), s05_peers.py (SIC / TF-IDF / named candidates), s06_jev.py,
  s07_backtest.py (DEV), leakage probe, PREREG.md, TEST once, README.md.
