# r3:xasset_dualmom_volcap — cross-asset dual momentum with a volatility cap

## Why the baseline fails in 2008–2015
The template baseline holds the top five ETFs by 12-1 momentum, equal weight. Diagnosed with `diag.py`, `months.py` and `contrib.py`:
- **It crowds into one volatile factor.** It entered 2008 100% in EM and commodity-country equities (EWZ, FXI, EEM, EWA, EWC). It then rotated into commodities (DBC, DBA, SLV, GLD, XME) just before their 2008 H2 crash. In 2008 it lost −34%, and −13 points came from real assets alone.
- **Raw momentum in a mixed universe picks the highest-vol assets.** SLV, GDX, XME and EWZ sit at the top rank for months. That caused the 2011 loss (−18% vs SPY +2%), when silver and commodities reversed.
- **It is slow to come back after a crash.** In 2009 the 12-1 winners were Treasuries and UUP, so the book missed the equity rebound (+11% vs +26%).
- **Asset-class caps don't fix it.** The commodity bet spans the "real", "industry" (XME, GDX) and "intl" (EWZ, EWA) classes, so a cap by class misses it (C04).

The biggest single lever was the volatility of the names chosen, not the momentum signal.

## The strategy (`strategy.py`)
The universe is all 56 ETFs except VIXY, which was excluded before any test because long VIX futures carry a structural negative roll. The book is built from four staggered monthly tranches, refreshed on trading days 0, 5, 10 and 15 of each month; the portfolio is their equal average. Each tranche does four things:
1. **Relative strength.** Rank the eligible ETFs by 12-1 momentum. Hold the top fifth (k = round(n/5)) with rank weights. This is the round-2 construction, unchanged.
2. **Trend gate (absolute momentum).** A pick keeps its slot only if its excess return over T-bills is positive, averaged over 1, 3 and 12 months (time-series momentum blend, no skip).
3. **Volatility cap.** Each kept slot is scaled by min(1, 20% / its annualised 63-day vol). This trims silver, miners, single-country EM and crashing commodities. Weight is never scaled up.
4. **Defensive fallback.** The weight freed by steps 2 and 3 goes, split equally, to the 2 best (by 12-1 momentum) of SHY, IEF, TLT, TIP and GLD whose own trend gate passes. If none passes, it stays in cash. Before 2003 no bond ETFs existed, so the fallback was cash.

It is long only, with Σw ≤ 1 and no fitting (`refit_every=None`). It passes the causality audit.

**Parameters.** Inherited from round 2: 12-1 lookback, top fifth, rank weights, 4 tranches. Set before testing: trend horizons 1/3/12 months (from the time-series momentum literature), the defensive set, 2 defensive holdings and the VIXY exclusion. Chosen with a sensitivity check: the vol cap of 20%, the middle of 15/20/25%.

## Results (harness CLI; `result_*.json`)
| CAGR | etf_dev 2000–15 | etf_dev_a 2000–07 | etf_dev_b 2008–15 |
|---|---:|---:|---:|
| **r3:xasset_dualmom_volcap** | **9.04%** | **11.18%** | **6.76%** |
| SPY buy & hold | 3.98% | 1.55% | 6.46% |
| 60/40 SPY/IEF | 5.05% | 3.54% | 6.61% |
| template baseline | 8.91% | 14.07% | 4.01% |

- It clears the bar: it beats SPY and 60/40 in both halves. In etf_dev_b the margin is only **+0.30 over SPY and +0.15 over 60/40**.
- It gives up about 3 points to the baseline in 2000–07 and gains about 2.7 points in 2008–15.
- Max drawdown in 2000–15 is −26.9%, against −55.2% for SPY.
- Calendar years (%): 2000 −9.9, 2001 −8.9, 2002 −3.4, 2003 31.7, 2004 9.8, 2005 30.1, 2006 27.8, 2007 22.4, 2008 −7.0, 2009 0.6, 2010 19.2, 2011 −5.8, 2012 9.0, 2013 31.3, 2014 12.9, 2015 0.7.
- Averages: defensive share 22%, cash 11%, largest single weight 23%. One-way turnover is about 3.4× a year before tranche smoothing.

## Everything tried (`evals.log`, 19 configurations, each run on etf_dev, etf_dev_a and etf_dev_b)
The log lives in this directory, not `research/evals.log`, because hard rule 1 allows writes only here. Every configuration is ranked by 12-1 momentum, holds the top fifth with rank weights across 4 tranches, and excludes VIXY, unless its row says otherwise.

| # | configuration | dev | dev_a | dev_b |
|---|---|---:|---:|---:|
| C01 | round-2 construction ported to the full universe | 8.10 | 12.52 | 3.87 |
| C02 | + 12-1 absolute filter, defensive fallback | 7.35 | 11.27 | 3.58 |
| C03 | C02 + rank × inverse-vol weights | 7.56 | 10.68 | 4.48 |
| C04 | C02 + 50% cap per asset-class group | 7.14 | 11.58 | 2.88 |
| C05 | C02 but the gate is the 1/3/12-month trend blend | 8.52 | 11.67 | 5.48 |
| C06 | C05 + rank by momentum/vol (Sharpe) | 5.95 | 7.21 | 4.65 |
| C07 | C05 with graded gate (fraction of horizons up) | 8.38 | 11.71 | 5.07 |
| C08 | C07 + inverse-vol weights | 8.18 | 11.33 | 4.98 |
| C09 | C05 without the 8 industry ETFs | 8.28 | 12.86 | 3.92 |
| C10 | C05 + skip picks with 126d correlation > 0.85 to a stronger pick | 8.62 | 12.04 | 5.28 |
| C11 | C05 ranked by the average of 6-1 and 12-1 | 8.91 | 12.24 | 5.54 |
| C12 | C05 + equity-breadth defensive share | 8.64 | 11.48 | 5.74 |
| C13 | C05 ranked by the 3/6/12-month average (no skip) | 8.77 | 12.29 | 5.30 |
| **C14** | **C05 + per-position vol cap 20% (final)** | **9.04** | **11.18** | **6.76** |
| C15 | vol cap 15% | 8.95 | 10.83 | 6.89 |
| C16 | vol cap 25% | 9.17 | 11.84 | 6.42 |
| C17 | C14 with top 15% | 8.75 | 10.78 | 6.59 |
| C18 | C14 with top 25% | 9.17 | 11.29 | 6.92 |
| C19 | C14, defensive ranked by trend blend | 9.04 | 10.98 | 6.96 |

**What the log shows:**
- Two changes did the work: the fast trend gate (C02 → C05, about +1.9 points in dev_b) and the vol cap (C05 → C14, about +1.3 points).
- The vol cap and the fraction held form a smooth surface. etf_dev_b runs 6.4–6.9 and etf_dev_a runs 10.8–11.8 across it, and the final choice is at the centre.
- Ranking faster, correlation filters, class caps, breadth timing and Sharpe ranking were all noise or harmful.

## Risks
- **The etf_dev_b margin is thin (+0.15 over 60/40).** Two of the four neighbouring configurations fail it: frac 15% gives 6.59, below 60/40, and vol cap 25% gives 6.42, below SPY. Expect the holdout to land near the benchmarks rather than clearly above them.
- **Selection bias from 19 looks.** The two effective changes were motivated by the diagnosis, but only the vol cap was tuned (3 values).
- **Lag after a crash.** The 2009 rebound was mostly missed (+0.6%). A sharp V-shaped recovery costs CAGR.
- **Heavy gold and Treasury exposure.**
  * GLD can be both a momentum pick and the defensive fallback. Today it is 41% of the book.
  * A joint fall in bonds and gold while equities trend down (as in 2022) has no hiding place except cash.
- **The early years are not comparable.** Before 2003 the universe was equity only and the fallback was cash (2000–02: −9.9 / −8.9 / −3.4%).
- **Costs.** DBC, DBA, UUP and BWX cost 10 bp and PBP 25 bp. These are included in the results, but live fills on thin ETFs may be worse.

## Live orders (`python -m harness.live strategies/r3_cross_asset/strategy.py --capital 100000`, 2026-09-23)
```
r3:xasset_dualmom_volcap: target set on 2026-09-23 (latest data 2026-09-23)
ticker    weight     price  shares
GLD        41.3%    392.88     105
SOXX       10.7%    565.72      18
SLV         9.8%     58.16     168
XLE         8.3%     62.37     133
IBB         7.1%    206.60      34
DBC         6.6%     32.88     199
XLK         5.5%    195.34      28
EEM         2.8%     67.71      41
IWD         2.7%    251.42      10
XME         1.4%    109.58      12
EWZ         1.4%     37.37      37
GDX         1.2%     93.56      13
IWM         1.1%    281.92       4
cash (T-bills): 0.0%
```

## Files
- `strategy.py`: the final strategy, self-contained.
- `xasset.py`: the parameterised research engine.
- `evalcfg.py`: runs a configuration and appends it to `evals.log`.
- `yearly.py`, `months.py`, `contrib.py`, `diag.py`: diagnostics of logged configurations. They are not new configurations.
