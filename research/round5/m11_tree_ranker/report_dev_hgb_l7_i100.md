# DEV report: hgb_l7_i100 (holding months 2013-12-31+1m .. 2019-11-29+1m)

| variant | CAGR | vs SPY (pts) | maxDD | vol | Sharpe(0rf) |
|---|---|---|---|---|---|
| SPY (buy & hold) | 12.2% | +0.0 | -13.7% | 12.4% | 1.00 |
| EW universe, 1x cost | 11.1% | -1.1 | -15.6% | 13.6% | 0.84 |
| ctrl 12-1 momentum top25, 1x cost | 8.4% | -3.9 | -27.8% | 17.4% | 0.55 |
| MODEL top25, 1x cost | 8.4% | -3.8 | -27.7% | 16.9% | 0.56 |
| MODEL top25 + SPY trend switch, 1x cost | 6.7% | -5.5 | -23.1% | 14.6% | 0.52 |
| ctrl momentum + trend switch, 1x cost | 6.4% | -5.9 | -26.4% | 16.1% | 0.46 |
| EW universe, 2x cost | 11.0% | -1.2 | -15.6% | 13.6% | 0.84 |
| ctrl 12-1 momentum top25, 2x cost | 7.4% | -4.8 | -28.0% | 17.4% | 0.50 |
| MODEL top25, 2x cost | 6.5% | -5.7 | -28.7% | 16.8% | 0.46 |
| MODEL top25 + SPY trend switch, 2x cost | 4.9% | -7.4 | -24.2% | 14.6% | 0.40 |
| ctrl momentum + trend switch, 2x cost | 5.3% | -6.9 | -26.6% | 16.1% | 0.40 |

Survivorship / missing-price scenarios (model top25, 1x cost):

| scenario | CAGR | vs SPY | maxDD | vol | Sharpe |
|---|---|---|---|---|---|
| missing=drop, series-ends-in-hold=last | 8.4% | -3.8 | -27.7% | 16.9% | 0.56 |
| missing=drop, series-ends-in-hold=m50 | 8.4% | -3.8 | -27.7% | 16.9% | 0.56 |
| missing=drop, series-ends-in-hold=m100 | 8.4% | -3.8 | -27.7% | 16.9% | 0.56 |
| missing=neutral, series-ends-in-hold=last | 8.7% | -3.6 | -23.8% | 15.8% | 0.60 |
| missing=x50, series-ends-in-hold=last | 6.3% | -6.0 | -25.3% | 15.9% | 0.46 |
| missing=x100, series-ends-in-hold=last | 3.9% | -8.3 | -26.7% | 16.0% | 0.32 |
| missing=x100, series-ends-in-hold=m100 | 3.9% | -8.3 | -26.7% | 16.0% | 0.32 |
| EW universe under the same worst case | 5.6% | -6.6 | -17.2% | 13.7% | 0.47 |
| momentum under the same worst case | 3.7% | -8.5 | -27.2% | 16.4% | 0.30 |

K sensitivity (1x cost, reported only; K=25 frozen):

| K | CAGR | vs SPY | maxDD | vol | Sharpe |
|---|---|---|---|---|---|
| K=10 | 11.3% | -0.9 | -32.5% | 19.3% | 0.65 |
| K=20 | 7.0% | -5.3 | -30.4% | 17.2% | 0.48 |
| K=25 | 8.4% | -3.8 | -27.7% | 16.9% | 0.56 |
| K=30 | 7.4% | -4.8 | -28.3% | 16.9% | 0.51 |
| K=50 | 9.0% | -3.3 | -23.0% | 16.1% | 0.61 |
| K=100 | 9.5% | -2.7 | -17.1% | 15.7% | 0.66 |

Calendar-year net returns (1x cost):

| t1 | model | mom | ew | spy |
|---|---|---|---|---|
| 2014 | 12.9 | 3.2 | 11.9 | 14.1 |
| 2015 | -8.9 | 11.2 | 4.1 | 4.5 |
| 2016 | 4.3 | -0.9 | 12.7 | 6.5 |
| 2017 | 12.6 | 25.4 | 20.6 | 22.9 |
| 2018 | 7.8 | -1.3 | 4.1 | 7.5 |
| 2019 | 17.8 | 7.8 | 9.8 | 13.8 |
| 2020 | 6.0 | 6.7 | 4.0 | 4.8 |

Monthly rank IC (Spearman, score vs next-month return, eligible universe):

| signal | mean IC | t-stat | % months > 0 | months |
|---|---|---|---|---|
| model score | -0.0063 | -0.39 | 50% | 72 |
| 12-1 momentum | -0.0045 | -0.20 | 49% | 72 |
| model minus momentum (paired) | -0.0018 | -0.05 | 50% | 72 |

Top25 gross minus EW-universe gross: mean -0.02%/month, t -0.08

Avg one-way turnover/month (model): 74% ; momentum: 38%
Distinct position entries (trades in): 1332 over 72 months; avg cost drag 1.78%/yr at 1x
Least-liquid holding's median daily $ volume: median $10M (10th pct month $5M). At 5% of ADV per name per rebalance day -> capacity ~ 25 x 5% x $5M = $7M per day of trading
Share of S&P 500 names in model book: 59%

Average cross-sectional percentile of model holdings per feature (0.5 = neutral):

|  | mom12_1 | mom6_1 | rev1 | resmom | hi52 | vol1 | vol12 | maxret1 | beta | ivol | secmom | size_dv | dv_trend | amihud | logprice | short_ratio | short_chg | is500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pctile | 0.46 | 0.36 | 0.34 | 0.63 | 0.32 | 0.61 | 0.64 | 0.55 | 0.59 | 0.64 | 0.5 | 0.49 | 0.42 | 0.54 | 0.26 | 0.43 | 0.45 | 0.49 |

Permutation importance (mean drop in monthly rank IC when the feature is shuffled; positive = the model uses it and it helps OOS):

|  | ic_drop_mean | t |
|---|---|---|
| rev1 | 0.0104 | 1.7786 |
| hi52 | 0.0023 | 1.2286 |
| size_dv | 0.0014 | 0.9595 |
| beta | 0.0011 | 0.3758 |
| short_ratio | 0.0005 | 1.2479 |
| logprice | 0.0005 | 0.1015 |
| short_chg | 0.0002 | 0.4728 |
| is500 | -0.0001 | -0.1298 |
| resmom | -0.0001 | -0.1943 |
| dv_trend | -0.0004 | -0.4065 |
| vol1 | -0.0008 | -0.3795 |
| vol12 | -0.0011 | -0.8669 |
| mom12_1 | -0.0013 | -0.317 |
| mom6_1 | -0.0014 | -0.3475 |
| maxret1 | -0.0021 | -1.6668 |
| amihud | -0.0026 | -2.7969 |
| ivol | -0.0032 | -1.8415 |
| secmom | -0.008 | -0.6966 |

Single-feature monthly rank ICs (raw feature vs next-month return):

| feature | mean_ic | t |
|---|---|---|
| mom12_1 | -0.0045 | -0.1959 |
| mom6_1 | 0.0081 | 0.3848 |
| rev1 | -0.0324 | -1.87 |
| resmom | 0.0207 | 1.854 |
| hi52 | 0.0003 | 0.0136 |
| vol1 | -0.0157 | -0.7324 |
| vol12 | -0.0206 | -0.8002 |
| maxret1 | -0.0179 | -1.0382 |
| beta | -0.0061 | -0.1955 |
| ivol | -0.0191 | -0.9882 |
| secmom | -0.0172 | -0.7781 |
| size_dv | 0.005 | 0.3598 |
| dv_trend | -0.0005 | -0.0447 |
| amihud | -0.0093 | -0.5594 |
| logprice | -0.0059 | -0.457 |
| short_ratio | -0.0131 | -0.8115 |
| short_chg | -0.0118 | -0.839 |
| is500 | 0.0084 | 0.6381 |
