# m11 tree ranker: STATUS

## Done
- (2026-09-24) Read BRIEF; inspected inputs. m06 S&P 500 intervals only start 2019-10 and m06 prices start 2019-09,
  so I rebuild S&P 500 PIT membership from 2011-12 myself (from m06's saved Wikipedia HTML, read-only) and fetch
  missing prices with yfinance into data/round5/m11_tree_ranker/.
- FINRA: CNMS consolidated files exist only from 2018-08; before that use FNSQ+FNYX+FNQC+FORF facility files.

## Next step
- s01_universe.py (S&P 500 PIT monthly membership 2011-12..now) -> s02_prices.py -> s03_finra.py -> s04_features.py
