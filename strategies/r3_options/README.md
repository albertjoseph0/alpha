# r3:options_switch210_mom5_sharpe7: option-income and defensive funds (round 3)

## Short answer to the brief
**In this universe and period, the option-income ETFs do not raise CAGR, and neither do USMV or VIXY.**
The submitted strategy is a trend-switched momentum core that keeps them as ordinary candidates. It
almost never picks them, and removing them changes nothing (config 18 = config 14 to 0.01 pt).
The strategy clears the bar in both halves, but the dev_b margin depends on the chosen trend
length (see Risks).

## 1. Covered call vs underlying (overlapping dev history, daily total returns, no costs)

| fund vs underlying | overlap | fund CAGR | underlying CAGR | fund vol / maxDD | underlying vol / maxDD | beta | alpha vs beta-matched mix* |
|---|---|---:|---:|---|---|---:|---:|
| PBP vs SPY | 2008-01 → 2015-12 | 2.64% | 6.36% | 17.0% / −43% | 22.1% / −52% | 0.57 | −1.0%/yr |
| XYLD vs SPY | 2013-06 → 2015-12 | 8.60% | 12.70% | 11.2% / −12% | 12.8% / −12% | 0.72 | −0.3%/yr |
| QYLD vs QQQ | 2013-12 → 2015-12 | 5.86% | 16.08% | 10.7% / −11% | 15.9% / −14% | 0.53 | −2.3%/yr |
| USMV vs SPY | 2011-10 → 2015-12 | 14.71% | 15.02% | 10.7% / −9.5% | 13.6% / −12% | 0.70 | — |
| VIXY vs SPY | 2011-01 → 2015-12 | **−49.2%** | 12.14% | 65% / −98% | 15% / −19% | −3.5 | — |

\*Beta-matched mix = β·underlying + (1−β)·T-bills. A negative number means the fund earned less than
the plain stock and cash mix with the same beta. The option premium does not show up net of fees.

- **Theory holds on the downside and in flat years.** PBP helped in the flat years 2011 (+4.4% vs +1.9%)
  and 2015 (+4.1% vs +1.2%), and fell less in 2008 (−29% vs −37%).
- **It lags badly in up years.** PBP gained 4.9% in 2010 against SPY's 15.1%, 4.5% against 16.0% in
  2012, and 12.9% against 32.3% in 2013. QYLD gained 3.4% in 2014 against QQQ's 19.2%.
- **Regime conditioning** used SPY's 210-day trend and 21-day realised vol against its expanding
  median, applied with a 2-day lag.
  - In SPY downtrends, PBP still lagged SPY by 1.8%/yr, because the 2009 rebound sits inside the
    downtrend regime.
  - The only positive beta-adjusted cell was downtrend with high vol (+3%/yr), and the sample is small.
  - The XYLD and QYLD samples (2–2.5 years) are far too short to test regimes. Six to 42 days of
    downtrend is noise.
- **PBP is thinly traded.** Its lag-1 autocorrelation is −0.16 (bid-ask bounce), and the harness
  charges 25 bp per unit of turnover.
- **The data has no implied volatility** (no VIX index; VIXY only from 2011), so an IV-regime
  switch can't be tested. Realised vol is the only proxy.

## 2. Can the covered-call trade-off be exploited? (harness, net of costs)
| config | etf_dev | dev_a | dev_b |
|---|---:|---:|---:|
| SPY, switch to PBP once listed (always) | 1.99% | 1.55% | 2.43% |
| SPY; PBP when SPY 210d trend < 0 | 3.35% | 1.55% | 5.17% |
| SPY; PBP when 21d vol > median | 2.07% | 1.55% | 2.58% |
| SPY buy & hold | 3.98% | 1.55% | 6.46% |

None of the three switches beats plain SPY. dev_a is just SPY here, because PBP was not yet listed.

## 3. Low vol (USMV) and long VIX (VIXY)
- **USMV** matched SPY's return (14.7% vs 15.0%) with about 30% less volatility in 2011–15. It
  lowers risk but doesn't raise CAGR. No strategy picked it often enough to matter: it was held on 37
  days, at an average weight of 0.1%.
- **VIXY** lost 49%/yr. Admitted as a momentum candidate (config 8) it is never selected. A fixed
  hedge weight w costs roughly 0.5·w per year in CAGR. Consistent with round 1, crash protection
  bought this way costs CAGR.
- **What helps defensively is bonds, gold and defensive sectors**, chosen by a risk-adjusted
  (Sharpe) momentum score, not option or VIX products. That is the defensive sleeve of the strategy.

## The submitted strategy
`strategy.py` → `TrendSwitchMomentum` (no-argument constructor).
- **Regime:** SPY's 210-trading-day (~10-month) total return, read on each tranche day. Faber's
  10-month rule, set a priori.
  - **Up (> 0), offense:** plain 12-1 momentum over all ETFs except VIXY. Top 5, equal weight.
  - **Down, defense:** Sharpe momentum, i.e. 12-1 log return divided by 12-month realised vol. Top 7,
    equal weight. It holds mostly Treasuries, IG and muni bonds, TIPS, gold, XLV and XLP. It is fully
    invested and never in cash by rule.
- **Construction:** 4 staggered monthly tranches (trading days 0/5/10/15), from the round-2 lesson.
  - Eligibility: at least 250 valid days in the last 252, and valid on each of the last 5 days.
  - Option-income funds and USMV are ordinary candidates.
- **Parameters:** trend length 210, k_on 5, k_off 7, and 4 tranches. The 12-1 lookback is inherited
  from the baseline. The strategy is long only, with Σw = 1 and no leverage.

### CAGR (harness CLI, net of costs; result_*.json)
| | etf_dev 2000–15 | etf_dev_a 2000–07 | etf_dev_b 2008–15 |
|---|---:|---:|---:|
| **r3:options_switch210_mom5_sharpe7** | **10.64%** | **13.82%** | **7.58%** |
| SPY buy & hold | 3.98% | 1.55% | 6.46% |
| 60/40 SPY/IEF | 5.05% | 3.54% | 6.61% |
| template baseline (top-5 12-1, monthly) | 8.91% | 14.07% | 4.01% |

It beats SPY and 60/40 in both halves. Against the baseline it gives up 0.25 pt in dev_a and gains
3.6 pt in dev_b.

The table below uses a simple gross backtest, without costs. Max drawdown was −39%, against SPY's −55%.
Annual volatility was about 20%. The strategy was in offense 71% of days.

| year | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| strategy % | −12.0 | −6.7 | −10.0 | 43.2 | 13.7 | 33.4 | 31.1 | 32.8 | −14.2 | 10.5 | 21.3 | −10.3 | 16.5 | 34.4 | 15.3 | 0.3 |
| SPY % | −9.7 | −11.8 | −21.6 | 28.2 | 10.7 | 4.8 | 15.8 | 5.1 | −36.8 | 26.4 | 15.1 | 1.9 | 16.0 | 32.3 | 13.5 | 1.2 |

In 2000–02 no bond ETF existed yet, so defense held defensive sectors.

## Everything evaluated (21 configurations of the 25 allowed; `evals.log`, produced by `research.py`)
CAGR in %, net of costs. "4tr" means four staggered tranches, and "noDEF" excludes PBP, XYLD, QYLD,
JEPI, USMV and VIXY.

| # | config | dev | dev_a | dev_b |
|---:|---|---:|---:|---:|
| 1 | baseline replica: mom top-5, 1 tranche, all ETFs | 8.91 | 14.07 | 4.01 |
| 2 | SPY → PBP always (once listed) | 1.99 | 1.55 | 2.43 |
| 3 | SPY / PBP by SPY 210d trend | 3.35 | 1.55 | 5.17 |
| 4 | SPY / PBP by 21d vol regime | 2.07 | 1.55 | 2.58 |
| 5 | baseline, noDEF | 8.91 | 14.07 | 4.01 |
| 6 | Sharpe-mom top 7, 4tr | 7.15 | 9.09 | 5.18 |
| 7 | #6 noDEF | 7.16 | 9.09 | 5.19 |
| 8 | #6 with VIXY as candidate | 7.15 | 9.09 | 5.18 |
| 9 | Sharpe-mom top 5 | 6.67 | 8.57 | 4.73 |
| 10 | Sharpe-mom top 10 | 6.45 | 8.43 | 4.43 |
| 11 | Sharpe-mom top 7, inverse-vol | 5.97 | 6.62 | 5.25 |
| 12 | mom top 7, 4tr | 8.20 | 13.00 | 3.57 |
| 13 | 50/50 blend of mom5-4tr and Sharpe7 | 7.88 | 11.41 | 4.45 |
| **14** | **switch 210d: mom5 / Sharpe7 (submitted)** | **10.64** | **13.82** | **7.58** |
| 15 | switch 126d | 9.03 | 11.97 | 6.19 |
| 16 | switch 252d | 9.77 | 13.80 | 5.91 |
| 17 | switch 210d, offense top 7 | 10.15 | 13.44 | 6.93 |
| 18 | #14 noDEF | 10.64 | 13.82 | 7.58 |
| 19 | switch 210d, defense = cash | 11.26 | 15.87 | 6.86 |
| 20 | switch, trend ensemble of 126/189/252 days, Sharpe defense | 9.72 | 13.23 | 6.36 |
| 21 | same ensemble, cash defense | 10.09 | 14.54 | 5.85 |

The descriptive covered-call statistics in sections 1 and 3 were computed on the raw data. They are
not strategy backtests.

## Risks and what the data cannot support
- **The dev_b pass is not robust to the trend length.**
  - The a priori value of 210 days is the peak of the tested surface.
  - At 126 days, at 252 days and with the 126/189/252 ensemble, dev_b lands between 5.9% and 6.4%.
    That is just below SPY's 6.46%, although still far above the baseline's 4.0%.
  - dev_a clears the bar everywhere, at 12–16%.
  - Expect the holdout edge over SPY to be smaller than the dev_b figure suggests. It could be
    negative in a strong, steady US bull market.
- **Whipsaw.** The regime flips about 36 times in 16 years, and each flip turns over most of the book.
  - Losing years: 2011 (−10% vs SPY +2%) and 2000–02, when defensive sectors fell too.
  - Fast V-shaped rebounds are missed, as in 2009 (+10.5% vs +26%).
- **Concentration.** Five equal-weight names in offense, and these can be commodity or single-country
  funds.
  - Today's live book is 40% SOXX + SLV and 30% commodity/miners.
  - Drawdowns of −39% have happened, and larger ones are possible.
- **The defensive sleeve depends on bonds hedging equities.** That held in 2000–2015. Because the
  sleeve uses Sharpe momentum, it rotates to whatever is trending smoothly (for example SHY, UUP or
  DBC) if bonds fall, but it lags.
- **The option-fund conclusions rest on short samples.** They are about 8 years for PBP, a thin and
  costly fund, and 2–2.5 years for XYLD and QYLD. JEPI has no dev data at all.
  - The samples cannot rule out a regime (e.g. a long, flat, high-IV market) where covered calls win.
  - They can say only that nothing in 2008–2015 suggests they raise CAGR.
  - A test of implied-vol timing is impossible without IV data.
- **Log location.** The brief asked for research/evals.log, but hard rule 1 forbids writing outside
  this directory. The log is therefore `strategies/r3_options/evals.log`.

## Live output (`harness.live --capital 100000`, run 2026-09-23)
```
r3:options_switch210_mom5_sharpe7: target set on 2026-09-23 (latest data 2026-09-23)
ticker    weight     price  shares
SOXX       20.0%    565.72      35
SLV        20.0%     58.16     343
IBB        15.0%    206.60      72
XLE        15.0%     62.37     240
XLK        10.0%    195.34      51
DBC        10.0%     32.88     304
GLD         5.0%    392.88      12
GDX         5.0%     93.56      53
cash (T-bills): 0.0%
```
The book is currently in offense: SPY's 10-month trend is up. The weights are the average of the 4
tranches. Not financial advice.

## Files
`strategy.py` (the strategy), `research.py` (all 21 configurations), `evals.log`, `result_etf_dev*.json`.
