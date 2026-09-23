# Round 3: tradeable ETF strategies (CAGR, net of per-ETF costs, long only, no leverage)

Holdout = 2016-01-04 → 2026-09-23, sealed until each strategy was frozen; one run each.

| strategy | holdout 2016–26 | dev 2000–15 | dev_a 2000–07 | dev_b 2008–15 | max DD (holdout) |
|---|---:|---:|---:|---:|---:|
| **r3:options_switch210_mom5_sharpe7** | **16.90%** | 10.64% | 13.82% | 7.58% | −25.7% |
| template: top-5 12-1 momentum | 15.11% | 8.91% | 14.07% | 4.01% | |
| r3:eqrot_mom12_dedup90_rank5_stag4_trend6IEF | 12.24% | 9.84% | 12.57% | 7.23% | −28.5% |
| r3:xasset_dualmom_volcap | 9.69% | 9.04% | 11.18% | 6.76% | −28.2% |
| buy & hold SPY | 14.99% | 3.98% | 1.55% | 6.46% | −33.7% |
| 60/40 SPY/IEF | 9.58% | 5.05% | 3.54% | 6.61% | −21.2% |
| equal-weight all ETFs | 10.11% | 4.68% | 5.58% | 3.81% | |

Holdout calendar years (%):

| year | SPY | 60/40 | r3_options | r3_eqrot | r3_xasset |
|---|---:|---:|---:|---:|---:|
| 2016 | 13.6 | 8.4 | 0.5 | 10.0 | −5.3 |
| 2017 | 21.7 | 13.8 | 25.1 | 20.9 | 21.2 |
| 2018 | −4.6 | −2.1 | −6.8 | −1.0 | −3.3 |
| 2019 | 31.2 | 22.0 | 19.0 | 16.8 | 12.0 |
| 2020 | 18.3 | 16.3 | 12.8 | 4.9 | 3.9 |
| 2021 | 28.7 | 15.1 | 18.7 | 15.8 | 13.2 |
| 2022 | −18.2 | −16.7 | 12.6 | −7.6 | −3.1 |
| 2023 | 26.2 | 16.8 | 19.7 | 14.9 | 10.8 |
| 2024 | 24.9 | 14.3 | 12.6 | 6.5 | 13.1 |
| 2025 | 17.7 | 13.9 | 52.0 | 38.2 | 39.6 |
| 2026 (to Sep) | 13.5 | 6.9 | 23.9 | 18.2 | 8.9 |

Findings:
* Only r3_options beat SPY out of sample, by +1.9 points a year with a smaller drawdown. It lost to
  SPY in 7 of 11 years. Its whole margin comes from 2022 (+12.6% vs −18.2%) and 2025 (+52% vs +17.7%).
  Its dev result was fragile: other trend lengths fell just short of SPY in 2008–15.
* The covered-call ETFs (PBP, XYLD, QYLD, JEPI) didn't raise CAGR and were almost never selected.
* All three round-3 strategies beat 60/40, and the two with crash protection lagged SPY in the
  strong US bull market.
