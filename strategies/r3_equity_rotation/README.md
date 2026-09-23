# r3:eqrot_mom12_dedup90_rank5_stag4_trend6IEF: equity-group momentum rotation on real ETFs

## Idea
The strategy ranks every equity ETF in the universe by 12-1 momentum and holds the top fifth, using the round-2 construction. Near-duplicate funds are skipped. Any pick that is not trending up hands its weight to IEF.

- **Universe:** 37 ETFs, fewer in early years before later funds list.
  - US size and style funds: SPY, QQQ, MDY, IWM, IWD, IWF, USMV, MTUM.
  - SPDR sectors, including XLRE and XLC once listed.
  - Industry funds: SOXX, IBB, ITB, KRE, XME, GDX, IGV, ITA.
  - Country and region funds: EFA, EEM, EWJ, VGK, EWZ, FXI, INDA, EWC, EWA.
  - VNQ (US REITs).

  About 15 funds are eligible in 2000 and about 33 in 2015. Bonds, commodities, option-income funds and VIX are never ranked.

Each tranche applies these steps:
1. **Signal.** 12-1 momentum: the log total return from t-252 to t-21. A fund is eligible if it has at least 250 valid days out of the last 252 and a valid return on each of the last 5 days.
2. **Holdings.** k = max(3, round(n/5)).
3. **De-duplication.** Walk down the ranking. Skip any candidate whose 252-day daily-return correlation with an already chosen fund is above 0.90. This stops SPY, IWF, QQQ and XLK, for example, from filling several slots.
4. **Weights.** Linear in rank among the k picks, normalised.
5. **Trend check.** A pick whose **6-month** return (t-126 to t, no skip) does not beat T-bills hands its weight to **IEF**. If IEF fails the same check, or is not yet listed, that weight goes to T-bill cash.
6. **Four staggered tranches.** Tranches are refreshed monthly on trading days 0, 5, 10 and 15. The portfolio is their average.

The strategy is long only, uses no leverage and is causal (it passes the audit).

**Parameters:**
- Inherited a priori from round 2: 12-1 lookback, top 1/5, rank weights, 4 tranches.
- Set a priori here: correlation cap 0.90, k_min 3, IEF as fallback.
- Chosen after the first failure: 6-month trend window. This is the middle of the 3/6/9-month range, all of which pass. See the log below.

## Results (harness CLI, net of per-ETF costs; result_*.json)
| | etf_dev 2000–15 | etf_dev_a 2000–07 | etf_dev_b 2008–15 |
|---|---:|---:|---:|
| **r3:eqrot (this)** | **9.84%** | **12.57%** | **7.23%** |
| SPY buy & hold | 3.98% | 1.55% | 6.46% |
| 60/40 SPY/IEF | 5.05% | 3.54% | 6.61% |
| template baseline (top-5 12-1, all ETFs) | 8.91% | 14.07% | 4.01% |

It clears the bar in both halves, but **the dev_b margin is thin: +0.77 points over SPY and +0.62 over 60/40**. Max drawdown over 2000–15 is -36% (SPY -55%). The fallback averages 10% in IEF, and cash averages 12%, mostly before IEF has a 1-year history in mid-2003.

### Where the returns come from (honest decomposition)
| year | strat | SPY | | year | strat | SPY |
|---|---:|---:|---|---|---:|---:|
| 2000 | -9.6% | -9.8% | | 2008 | **-14.9%** | -36.8% |
| 2001 | -9.0% | -11.8% | | 2009 | 19.7% | 26.4% |
| 2002 | -10.8% | -21.6% | | 2010 | 9.6% | 15.1% |
| 2003 | 46.4% | 28.2% | | 2011 | -9.9% | 1.9% |
| 2004 | 3.0% | 10.7% | | 2012 | 21.3% | 16.0% |
| 2005 | 37.9% | 4.8% | | 2013 | 33.4% | 32.3% |
| 2006 | 31.3% | 15.8% | | 2014 | 10.4% | 13.5% |
| 2007 | 28.6% | 5.1% | | 2015 | -3.2% | 1.2% |

- **2000–07.** Selection works. The strategy rode EM, commodity and country funds (EWZ, FXI, EEM, XLE, EWA) through 2003–07. Pure selection without any trend check scores 14.02% in dev_a.
- **2008–15.** **Selection alone fails.** Pure equity-group momentum with no trend check scores **1.64% against SPY's 6.46%**. The strategy trails SPY in 2009, 2010, 2011, 2014 and 2015, because it was holding commodity equities (XME, GDX, XLE) and EM funds while US large caps led. The dev_b win comes entirely from the 6-month trend check moving to IEF during 2008.
- **Answer to the key question.** Equity-group momentum on real ETF breadth survives net of costs in 2000–07. **It does not survive in 2008–15 on its own.** The strategy passes the bar only with a relatively fast absolute-trend exit to Treasuries. Expect it to behave like a trend-filtered momentum fund: it adds value in trending and crashing markets and lags in V-shaped, US-led recoveries.

## Everything tried (research.py, research/evals.log): 16 configurations
Each configuration was run once on all three windows. CAGR in %:

| # | config | change | dev | dev_a | dev_b | passes? |
|---|---|---|---:|---:|---:|---|
| 1 | core | a-priori design, trend check on the 12-1 window | 7.40 | 12.77 | 2.35 | no |
| 2 | **trend6** | **trend check on the 6-month return (final)** | **9.84** | **12.57** | **7.23** | **yes** |
| 3 | sharpe | rank by momentum/vol, 12-1 trend | 5.89 | 9.10 | 2.83 | no |
| 4 | sharpe_trend6 | momentum/vol plus 6-month trend | 8.29 | 9.37 | 7.28 | yes |
| 5 | t6_no_trend | no trend check (pure selection) | 7.62 | 14.02 | 1.64 | no |
| 6 | t6_trend3 | 3-month trend | 10.33 | 12.71 | 8.02 | yes |
| 7 | t6_trend9 | 9-month trend | 9.56 | 11.74 | 7.47 | yes |
| 8 | t6_no_dedup | no correlation de-duplication | 9.68 | 12.48 | 7.02 | yes |
| 9 | t6_eqwt | equal weight instead of rank weight | 9.35 | 12.05 | 6.73 | yes (barely) |
| 10 | t6_single_tranche | one tranche on day 0 | 11.35 | 14.65 | 8.21 | yes |
| 11 | t6_us_only | drop international funds | 6.83 | 4.75 | 8.84 | no |
| 12 | t6_frac_1_3 | top third | 9.19 | 11.71 | 6.69 | yes (barely) |
| 13 | t6_corr_80 | correlation cap 0.80 | 9.71 | 13.81 | 5.76 | no |
| 14 | t6_trend_cash | failing slots go to cash, not IEF | 9.23 | 12.46 | 6.16 | no |
| 15 | t6_single_day10 | one tranche on day 10 | 8.67 | 10.71 | 7.87 | yes |
| 16 | t6_refresh4 | whole book recomputed on each of days 0/5/10/15 | 7.40 | 10.98 | 3.99 | no |

Lessons from the log:
- **A trend check faster than 12 months is the essential ingredient.** The 3, 6 and 9-month windows all pass. The 12-1 window, which is only as fast as the ranking signal, and no trend check both fail dev_b. Six months was taken from the middle, not the 3-month peak.
- **International breadth is essential for dev_a.** US-only scores 4.75%.
- **Vol-adjusted ranking hurts.** It gives up the EM boom, which matches the round-2 finding.
- **IEF beats cash as the fallback,** by 1.1 points in dev_b.
- **De-duplication at 0.90 and rank weights add about 0.1–0.2 and 0.5 points respectively.** These are small but consistent in all three windows. A 0.80 cap is too aggressive.
- **The single-tranche result is rebalance-day luck.** Day 0 scores 11.35 and day 10 scores 8.67, with stag4 in between at 9.84. Staggering was kept to average out that luck. Recomputing the whole book every week whipsaws and is worse.

## Risks
- **Thin dev_b margin, which depends on one crash year.** Outside 2008, the strategy lagged SPY in most of 2009–15. If the holdout (2016 onward) is a US-mega-cap-led bull market with sharp V-shaped dips, such as 2018Q4 and 2020, expect it to **trail SPY**. The trend check will exit near lows and re-enter late, and the selection tends to favour cyclical and EM funds.
- **Trend-window choice was made after seeing the failure of config 1.** Config 1 used the same window as the signal. The 3/6/9 range all pass, but the choice is still data-informed. The search used 16 configurations.
- **Concentration.** There are 3 to 7 names per tranche. Overlapping tranches can stack one fund above 30%, as with SOXX today. The funds held are often high-volatility industry or single-country ETFs: SOXX, XME, GDX, EWZ, FXI.
- **Rising rates hurt the fallback.** IEF worked as a hedge in 2000–15. It is protected only by its own 6-month trend check (otherwise cash).
- **Costs.** Target turnover is about 3–4× one-way per year. At 2–4 bp this is small, but real-world slippage on less liquid funds (XME, ITA, INDA) may be larger than modelled.

## Live orders (`python -m harness.live strategies/r3_equity_rotation/strategy.py --capital 100000`)
```
r3:eqrot_mom12_dedup90_rank5_stag4_trend6IEF: target set on 2026-09-23 (latest data 2026-09-23)
ticker    weight     price  shares
SOXX       31.2%    565.72      55
XLE        23.5%     62.37     376
IBB        14.3%    206.60      69
EEM         7.1%     67.71     105
GDX         4.2%     93.56      44
IWD         3.6%    251.42      14
XME         3.6%    109.58      32
IWM         0.9%    281.92       3
cash (T-bills): 11.6%
```
Cash is 11.6% because some picks failed the 6-month check while IEF also failed its own check. To implement, rebalance to these targets. Re-run the command on or after trading days 0, 5, 10 and 15 of each month; each run refreshes one of the four tranches.

## Files
- `strategy.py`: the strategy (no-argument constructor).
- `research.py`: every configuration in the log, reproducible.
- `result_etf_dev*.json`: harness CLI results.
