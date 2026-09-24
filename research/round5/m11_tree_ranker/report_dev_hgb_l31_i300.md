# DEV report: hgb_l31_i300 (holding months 2013-12-31+1m .. 2019-11-29+1m)

| variant | CAGR | vs SPY (pts) | maxDD | vol | Sharpe(0rf) |
|---|---|---|---|---|---|
| SPY (buy & hold) | 12.2% | +0.0 | -13.7% | 12.4% | 1.00 |
| EW universe, 1x cost | 11.1% | -1.1 | -15.6% | 13.6% | 0.84 |
| ctrl 12-1 momentum top25, 1x cost | 8.4% | -3.9 | -27.8% | 17.4% | 0.55 |
| MODEL top25, 1x cost | 8.2% | -4.0 | -20.2% | 16.7% | 0.55 |
| MODEL top25 + SPY trend switch, 1x cost | 4.4% | -7.9 | -20.0% | 14.1% | 0.37 |
| ctrl momentum + trend switch, 1x cost | 6.4% | -5.9 | -26.4% | 16.1% | 0.46 |
| EW universe, 2x cost | 11.0% | -1.2 | -15.6% | 13.6% | 0.84 |
| ctrl 12-1 momentum top25, 2x cost | 7.4% | -4.8 | -28.0% | 17.4% | 0.50 |
| MODEL top25, 2x cost | 6.0% | -6.2 | -21.4% | 16.7% | 0.43 |
| MODEL top25 + SPY trend switch, 2x cost | 2.3% | -9.9 | -21.2% | 14.1% | 0.23 |
| ctrl momentum + trend switch, 2x cost | 5.3% | -6.9 | -26.6% | 16.1% | 0.40 |

Survivorship / missing-price scenarios (model top25, 1x cost):

| scenario | CAGR | vs SPY | maxDD | vol | Sharpe |
|---|---|---|---|---|---|
| missing=drop, series-ends-in-hold=last | 8.2% | -4.0 | -20.2% | 16.7% | 0.55 |
| missing=drop, series-ends-in-hold=m50 | 8.2% | -4.0 | -20.2% | 16.7% | 0.55 |
| missing=drop, series-ends-in-hold=m100 | 8.2% | -4.0 | -20.2% | 16.7% | 0.55 |
| missing=neutral, series-ends-in-hold=last | 8.3% | -3.9 | -19.2% | 15.9% | 0.58 |
| missing=x50, series-ends-in-hold=last | 5.9% | -6.3 | -19.9% | 15.9% | 0.44 |
| missing=x100, series-ends-in-hold=last | 3.6% | -8.6 | -20.7% | 16.0% | 0.30 |
| missing=x100, series-ends-in-hold=m100 | 3.6% | -8.6 | -20.7% | 16.0% | 0.30 |
| EW universe under the same worst case | 5.6% | -6.6 | -17.2% | 13.7% | 0.47 |
| momentum under the same worst case | 3.7% | -8.5 | -27.2% | 16.4% | 0.30 |

K sensitivity (1x cost, reported only; K=25 frozen):

| K | CAGR | vs SPY | maxDD | vol | Sharpe |
|---|---|---|---|---|---|
| K=10 | 8.3% | -3.9 | -26.1% | 19.3% | 0.51 |
| K=20 | 8.4% | -3.8 | -20.5% | 17.3% | 0.55 |
| K=25 | 8.2% | -4.0 | -20.2% | 16.7% | 0.55 |
| K=30 | 10.3% | -2.0 | -19.2% | 16.5% | 0.68 |
| K=50 | 12.2% | +0.0 | -16.9% | 16.2% | 0.79 |
| K=100 | 11.7% | -0.6 | -15.9% | 15.6% | 0.78 |

Calendar-year net returns (1x cost):

| year | model | mom | ew | spy |
|---|---|---|---|---|
| 2014 | 12.1 | 2.9 | 13.5 | 14.5 |
| 2015 | -8.3 | 3.3 | -3.1 | -0.1 |
| 2016 | 20.5 | 13.1 | 24.2 | 15.7 |
| 2017 | 7.9 | 25.4 | 21.3 | 26.1 |
| 2018 | -16.6 | -20.7 | -12.1 | -9.5 |
| 2019 | 44.0 | 35.3 | 29.1 | 32.3 |

Monthly rank IC (Spearman, score vs next-month return, eligible universe):

| signal | mean IC | t-stat | % months > 0 | months |
|---|---|---|---|---|
| model score | 0.0034 | 0.24 | 49% | 72 |
| 12-1 momentum | -0.0045 | -0.20 | 49% | 72 |
| model minus momentum (paired) | 0.0080 | 0.27 | 50% | 72 |

Top25 gross minus EW-universe gross: mean -0.02%/month, t -0.10

Avg one-way turnover/month (model): 86% ; momentum: 38%
Distinct position entries (trades in): 1543 over 72 months; avg cost drag 2.03%/yr at 1x
Least-liquid holding's median daily $ volume: median $11M (10th pct month $5M). At 5% of ADV per name per rebalance day -> capacity ~ 25 x 5% x $5M = $6M per day of trading
Share of S&P 500 names in model book: 60%

Average cross-sectional percentile of model holdings per feature (0.5 = neutral):

|  | mom12_1 | mom6_1 | rev1 | resmom | hi52 | vol1 | vol12 | maxret1 | beta | ivol | secmom | size_dv | dv_trend | amihud | logprice | short_ratio | short_chg | is500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pctile | 0.47 | 0.4 | 0.36 | 0.6 | 0.35 | 0.6 | 0.62 | 0.56 | 0.59 | 0.61 | 0.51 | 0.51 | 0.43 | 0.52 | 0.37 | 0.47 | 0.5 | 0.5 |

Permutation importance (mean drop in monthly rank IC when the feature is shuffled; positive = the model uses it and it helps OOS):

|  | ic_drop_mean | t |
|---|---|---|
| rev1 | 0.0126 | 1.5705 |
| hi52 | 0.0044 | 1.3383 |
| vol12 | 0.004 | 1.1971 |
| vol1 | 0.0038 | 1.8305 |
| short_ratio | 0.0035 | 2.0491 |
| beta | 0.0021 | 0.5304 |
| logprice | 0.0016 | 0.4252 |
| size_dv | 0.0004 | 0.3099 |
| is500 | 0.0003 | 0.3882 |
| amihud | -0.0004 | -0.2036 |
| mom6_1 | -0.0006 | -0.1284 |
| maxret1 | -0.0009 | -0.3815 |
| dv_trend | -0.001 | -0.5739 |
| short_chg | -0.0012 | -0.8348 |
| mom12_1 | -0.0032 | -0.8271 |
| resmom | -0.004 | -1.3659 |
| ivol | -0.0059 | -1.3897 |
| secmom | -0.0096 | -0.9638 |

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
| short_ratio | -0.0113 | -1.307 |
| short_chg | 0.0004 | 0.0611 |
| is500 | 0.0084 | 0.6381 |
