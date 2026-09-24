# o01 activist 13D + Jev: STATUS (written by the orchestrator at hand-over)

## Done
- s01_list.py: EDGAR full-text search listing of initial SC 13D (and SCHEDULE 13D from Dec 2024), 2013-01..2026-08.
  A background process may still be running (`pgrep -af s01_list`, log data/orch/o01_activist_13d/s01.log);
  when it finishes it writes data/orch/o01_activist_13d/filings.csv. If the process is gone and there is no
  filings.csv, re-run it: the SEC responses are cached, so the re-run is fast.
- s02_text.py (Item 4 + percent of class extraction; tested on samples), s03_prices.py (yfinance), and
  s04_jev.py (Jev intent/hostility/letter/undervalued/agreement/demand questions on the anonymized Item 4, a
  filer-type question that sees only the filer names, and a leakage probe) are written but not run.

## Known issues
- The subject ticker comes from EDGAR's CURRENT display names. Delisted or acquired targets have no ticker,
  which is survivorship bias. Report the fraction without a ticker and bound the result.
- The Jev service returned a transient 503 once; jev.py now retries 10× with backoff.

## Next steps
1. filings.csv, then s02_text.py, s03_prices.py and s04_jev.py (Jev budget "o01" = $3).
2. Event study plus a calendar-time portfolio. Entry at the close of the first trading day AFTER file_date.
   Hold 63/126/252 days, equal-weight, long-only. Round-trip costs of 50bp for small caps, and 2×.
   Benchmarks: IWM, SPY, and all 13Ds (no text).
3. Feature sets: (a) no text (stake %, size, prior return); (b) keyword rules; (c) + Jev. DEV = filings 2014–2019;
   TEST = 2020+ (sealed; PREREG.md first).
4. README.md with the verdict.
