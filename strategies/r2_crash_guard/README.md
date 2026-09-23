# r2:crashguard_plain49: crash-robust 49-industry momentum (result: no guard needed)

## Idea
My job was to reduce momentum-crash damage (prior losers rallying in sharp rebounds after bear
markets) while staying fully invested. First I measured how much CAGR the round-2 baseline loses in
rebound states. The answer is **almost nothing** on the 49-industry universe. Every guard I tested
either cost CAGR or only added noise. The final strategy is therefore plain 12-1 momentum with no
guard:

* on the first trading day of each month, rank the i49 industries with at least 250 valid days in
  the last 252;
* the score is the log return from t−252 to t−21 trading days;
* hold the top third, equal weight, fully invested.

It has 3 parameters (12 months, skip 1 month, top third), all textbook values set a priori, and
none of them were tuned here.

## Results (harness CLI, CAGR)

| | dev 1950–99 | dev_a 1950–74 | dev_b 1975–99 | early 1932–49 |
|---|---:|---:|---:|---:|
| **r2:crashguard_plain49** | **17.58%** | **15.08%** | **19.98%** | **15.97%** |
| baseline (12-1, 49 ind., top third) | 17.58% | 15.08% | 19.98% | 15.97% |
| buy & hold | 13.40% | 9.42% | 17.53% | 10.52% |

It is identical to the baseline and beats buy & hold in every window.

## Diagnosis: why the crash guard has nothing to recover (`research/diag.py`, `research/beta.py`)
I used the Daniel–Moskowitz panic state, known at each rebalance: the market's trailing
24-month return is below 0 ("bear"), and its 126-day volatility is above the trailing 10-year
median. The baseline's log excess return over buy & hold, per year, split by state:

| window | total | bear-state months | bear & market-up months (per month) |
|---|---:|---:|---:|
| dev_a | +5.01%/yr | −0.03%/yr (30 mo) | −0.22% |
| dev_b | +2.22%/yr | +0.20%/yr (11 mo) | +0.64% |
| early | +4.36%/yr | +0.68%/yr (74 mo) | +0.29% |

* Full-sample beta of the portfolio is 1.04 to 1.11. In bear states it is 0.93 to 1.10.
* Even in the top-decile market months (the rebounds), the baseline beats the market:
  +0.40%, +0.18% and +0.26% per month in dev_a, dev_b and early.
* The DM momentum crash comes mainly from the **short leg** of the long-short strategy (losers
  rallying). A broad, long-only winner basket barely carries it.
* The round-1 bad years (1975, 1950, 1954–55, 1996) were a 12-industry / concentrated-portfolio
  phenomenon. For 49-industry momentum, 1975 is not among the worst years relative to buy & hold.
  The worst years are 1955, 1951, 1984, 1983, 1939 and 1932, which are mostly narrow-leadership
  bull years and not rebounds.

## What I tried (all on dev_a / dev_b / early; 9 configurations including the baseline)

| # | variant (all fully invested) | dev_a | dev_b | early | verdict |
|---|---|---:|---:|---:|---|
| 1 | baseline | 15.08 | 19.98 | 15.97 | kept |
| 2 | bear state (mkt 24m < 0): 50% winners + 50% Mkt | 15.02 | 19.83 | 15.51 | costs in all 3 |
| 3 | dual momentum: winners with 12-1 < 0 replaced by Mkt | 14.93 | 19.91 | 16.05 | costs in 2 of 3 |
| 4 | residual momentum (Blitz–Huij–Martens; 36 × 21-day blocks, market beta, t-stat scaled) | 12.99 | 19.46 | 14.96 | worse |
| 5 | residual momentum, unscaled | 12.66 | 19.35 | 14.36 | worse |
| 6 | panic state: hold the top third by beta (tilt toward high-beta prior losers) | 14.21 | 20.58 | 16.69 | mixed |
| 7 | panic state: 50% winners + 50% high-beta third | 14.68 | 20.29 | 16.45 | mixed, rejected |
| 8 | beta floor: mix in the high-beta third when winner beta < 1 | 14.08 | 19.71 | 16.63 | costs in 2 of 3 |
| 9 | tracking-error scaling of the tilt vs Mkt (Barroso–Santa-Clara style, λ ≤ 1) | 14.16 | 19.64 | 15.28 | costs in all 3 |

Variant 7 was the only one that beat the baseline in 2 of 3 windows. I rejected it because a
year-by-year breakdown shows it is a large-swing beta-timing bet with about zero mean, not
insurance:

* dev_a: 1970 −5.8%, 1971 +5.2%, 1973 −3.4%, 1974 −4.6%;
* dev_b: 1975 +2.9%;
* early: 1932 −1.8%, 1937 +2.6%, 1938 +3.4%, 1940 +5.0%.

It pays only when a bear market ends, and loses when the bear market continues.

## Risks
* **Holdout rebounds.** No dev evidence supports adding a guard, but that also means no guard is
  in place. If a rebound after a bear market in 2000–26 has defensive, low-beta industries as the
  12-1 winners, the strategy will lag in that year. The beta diagnostics suggest the lag would
  be moderate (bear-state beta ≈ 0.93–1.10), not a long-short-style crash.
* **Drawdowns are market-like** (−42% to −46% in round 1), because the strategy is always fully
  invested.
* This entry duplicates the baseline. Its value is a negative result: crash guards on
  49-industry long-only momentum cost CAGR in-sample, so the team shouldn't spend holdout
  selection budget on them.

## Files
* `strategy.py`: final strategy.
* `result_*.json`: harness output.
* `research/lib.py`: fast loop through `harness.engine.simulate`.
* `research/diag.py`: state attribution.
* `research/beta.py`: beta decomposition.
* `research/cands.py`: variants 1 and 4–5. Variants 2–3 were run from an earlier version of this
  file.
* `research/panic.py`: variants 6–8 and the year-by-year breakdown.
* `research/te.py`: variant 9.

All research used data up to 1999-12-31 only.
