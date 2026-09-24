# j01 Lazy Prices + Jev: STATUS

## Done
- s01_universe.py: S&P 500 PIT membership from m11 (read-only) -> ticker/year -> CIK map (insider data sets from m05,
  point-in-time; fallback SEC current map / m06). DATA/universe_cik.csv, DATA/ticker_year_cik.csv (804 CIKs).
- extract.py: HTML -> text -> Risk Factors / MD&A / Legal sections (longest-span header matching). Checked on 10 docs.

## Running
- s02_filings.py: EDGAR submissions JSON per CIK -> DATA/submissions_rows.csv (resumable) -> DATA/filings.csv
  (10-K/10-Q filed while an S&P 500 member at the prior month-end). Log DATA/s02.log.

## Next
- s03_sections.py pilot (40 CIKs, 10-K 2013-2019), check extraction coverage and Jev token cost.
