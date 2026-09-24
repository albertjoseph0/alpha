# j11 customer-links momentum (Cohen-Frazzini with Jev-confirmed 10-K customer links): STATUS

Agent j11, Jev budget $1.50. DEV 2013-2019, TEST 2020+ (sealed until PREREG.md).
Code: research/round7/j11_customer_links/, data: data/round7/j11_customer_links/ (DATA).

## Done
- s01_universe.py: PIT S&P 500 (m11) U S&P 400 (m01) members with prices in m11 close.pkl -> DATA/universe.csv
  (1153 tickers, 1147 CIKs), DATA/members.csv. Survivorship hole (members without prices): 26% 2013-12,
  12% 2019-12, 4% 2024-12.

## Running
- s02_filings.py: submissions JSON per CIK -> DATA/filings_all.csv, DATA/cik_meta.csv (resumable). Log DATA/s02.log.

## Next
- s03: choose 10-Ks to fetch (SIC filter, stage-1 screen), fetch with cache=False, extract candidate snippets.
