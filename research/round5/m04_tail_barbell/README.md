# m04: Noah-effect tail barbell (Taleb/Spitznagel style), SPY plus far-OTM SPX puts

**Verdict: NO EDGE.** In my backtest, the barbell never beats 100% SPY after costs: 0 of 24 pre-registered configurations beat
it on DEV, 0 of 24 on TEST, and 0 of 48 in a wider post-test grid. The pre-registered rule made **-0.20 pts/yr**
on TEST (11.17% vs 11.37%) and -0.24 pts/yr on DEV. The real Cboe tail-hedge index VXTH says the same thing
without any model: it returned **+114% in 2020**, yet over 2008-2026 it made 10.05% vs 11.49% for the S&P 500 TR.
+20 pts/yr is out of reach even with perfect hindsight timing: the upper bound is +8 pts/yr on TEST and +5 on DEV.

## The idea and the rule tested
Hold the S&P 500 (SPY, total return) and spend a small annual budget on far out-of-the-money SPX puts. Roll them monthly,
and when a crash makes them explode, sell them and put the proceeds into stocks at crash prices. Spitznagel
(*Safe Haven*) argues that this raises the portfolio's geometric return, not only its safety.

Implementation (`backtest.py`):
- On the first trading day of each month, sell the previous tranche at the model bid. Then buy SPX puts with
  K = S(1 - depth), expiring on the 3rd Friday of month m + tenor, spending budget/12 of NAV at the ask.
- Optional monetization: sell a tranche when its model mark at t-1 is at least M times its cost. The trade happens at t, one day later.
  The proceeds go into SPY, and a fresh tranche is bought at once.
- All non-put money is in SPY. The only instruments are long puts, so the maximum loss on the sleeve is the premium paid.

## How the puts are priced (no historical option chains are available)
- **Pricer: the "linz" skew rule** (`pricing.py`, `linz_calib.py`, `calibrate_surface.py`). Implied volatility is
  ATM(T) x (1 + beta |z|^0.85) on the put side, with z = ln(K/F)/(ATM sqrt T). Every day, ATM30 and beta are solved so that the
  model's own CBOE-method 30-day variance equals VIX² and its CBOE-method skewness equals (100 - SKEW)/10. The ATM level at other
  tenors is solved to match the VIX / VIX3M / VIX6M / VIX1Y variance-swap curve.
- **Validation on a real chain (2026-09-22, from the previous instance).** For 15-46% OTM puts at 2-10 months,
  model/real mid is 0.85-1.16. The SSVI variant is 1.3-1.7x the real mid, and serves as the expensive-pricing case. Real bid-ask
  spreads for 25-35% OTM puts are about 12% of mid at 2 months, 6% at 3 months and 4% at 4-6 months. So the base half-spread of 2.5% is
  realistic for the 4-month rule, and the 2x case is the realistic one for 2-month puts.
- **Historical validation against the real PPUT index** (`pput_check.py`). PPUT holds the S&P 500 and buys a 5%-OTM 1-month put
  every month, at real traded prices. Replicating it with my model puts gives 7.21% vs PPUT's 7.63% CAGR over 1990-2026
  (yearly correlation 0.99). The mean yearly difference is -0.08 pts in the 1990s, -1.2 pts in 2000-07 and -0.2 pts in 2008-26.
  So the model is, if anything, slightly *expensive* near the money in history. There is no historical check of the 30%-OTM
  wing itself. That is the main unverifiable assumption.
- **How the calibration behaves in the 1990s.**
  - VIX3M (from 2006-07) and VIX1Y (from 2007-01) are missing earlier. They are proxied by ln X = a + b ln VIX, fitted on the DEV
    overlap only: VIX3M b = 0.83, residual sd 0.048; VIX1Y b = 0.66, sd 0.072. VIX6M is interpolated.
  - So the 1990s term structure is a deterministic function of VIX: it slopes upward in calm markets and inverts in stress, but it
    carries no independent term-structure information. TEST needs no proxies.
  - The calibrated wing steepness beta is lower in the 1990s (yearly means 0.21-0.32) than in the 2020s (0.36-0.41), because SKEW
    was lower then.
  - Calibration residuals exceed 1e-3 on 700 of 9,244 days, with a maximum of 0.06. The residuals are in log-variance and skewness units, so this is harmless.
- **Artifact found and fixed: SKEW noise.** The raw daily SKEW jumps around (for example 105 -> 132 in the flat July 1990
  market), and this made 30%-OTM model marks jump 10-100x with no market move. That produces fake "crash gains" and fake
  monetizations. The base surface therefore uses the trailing 21-day mean SKEW (`surface_s21.pkl`). The raw version is
  kept as the `rawskew` case, and it is indeed slightly *better* (+0.06 pts DEV), which is the noise-harvest artifact.
- **Tick case (1990s realism).** A half-spread of at least 0.05 points and an ask of at least 0.10 points. In 1990, SPX was at 300-400 and
  30%-OTM model prices were often below 0.05 points, so they could not really have been bought. This case costs an extra 0.14 pts/yr on DEV, and nothing on TEST.

## DEV (1990-01 → 2007-12): grid and selection (`grid_dev.py`, `grid_dev.csv`)
- 24 configurations: depth {20%, 30%} × tenor {2, 4 months} × budget {1%, 2%, 3.3%/yr} × monetize {none, 5x}.
  Each was run in 5 cost cases, and every run is logged.
- **None beat SPY in any case.** Excess vs SPY ranged from -0.24 to -1.92 pts/yr in the base case. The shortfall is about equal to
  the net premium bleed (premium paid minus sale proceeds, 0.2-1.8% of NAV per year).
- The best DEV tranche paid 7x. The 1990-2007 declines were either too small (1990, 1998) or too slow (2000-02) for
  20-30%-OTM puts to reach their huge payoffs. Maximum drawdown is essentially unchanged (-47%).
- Selected by the pre-registered rule (highest base DEV CAGR), which is simply the smallest bleed: **30% OTM, 4-month, 1%/yr, 5x monetize**.

| DEV 1990-2007 | CAGR | vs SPY | MaxDD |
|---|---:|---:|---:|
| 100% SPY | 10.27% | – | -47.5% |
| 97% SPY + 3% T-bills | 10.11% | -0.16 | -46.3% |
| 97/3 with cash deployed after a 20% drawdown | 10.07% | -0.19 | -47.0% |
| **Barbell, frozen rule, base** | 10.03% | **-0.24** | -47.0% |
| same, 2x spread | 9.99% | -0.28 | -47.1% |
| same, SSVI pricing | 10.02% | -0.25 | -46.9% |
| same, tick floor | 9.89% | -0.38 | -47.0% |
| Canonical Universa-like (30% OTM, 2m, 3.3%/yr, 5x) | 8.64% | -1.63 | -46.6% |

## TEST (2008-01 → 2026-09-22), run once after PREREG.md (`evaluate.py test`, `eval_test.csv`)
| TEST 2008-2026 | CAGR | vs SPY | MaxDD | CAGR excluding 2008 and 2020 |
|---|---:|---:|---:|---:|
| 100% SPY | 11.37% | – | -51.9% | 14.73% |
| 97% SPY + 3% T-bills | 11.11% | -0.26 | -50.7% | 14.35% |
| 97/3 with cash deployed after a 20% / 30% drawdown | 11.14% / 11.20% | -0.23 / -0.17 | -51.6% / -51.3% | 14.40% / 14.38% |
| **Barbell, frozen rule, base** | **11.17%** | **-0.20** | -51.4% | 14.43% |
| same, 2x spread | 11.13% | -0.24 | -51.5% | 14.39% |
| same, SSVI pricing / SSVI with 2x spread | 11.15% / 11.11% | -0.22 / -0.26 | -51.4% | 14.41% / 14.37% |
| Canonical Universa-like, base / 2x / SSVI | 10.43% / 10.29% / 10.43% | -0.94 / -1.08 / -0.94 | -50.4% | 13.39% |
| *Real VXTH index (VIX-call tail hedge)* | 10.05% | -1.32 vs SPY (-1.44 vs SP500TR) | -38.4% | 7.65% |
| *Real PPUT index (5% OTM puts, full hedge)* | 8.81% | -2.56 | -35.8% | 9.64% |

- Result against the pre-registered criterion: base -0.20, x2 -0.24, SSVI -0.22. **NO EDGE.**
- Grid on TEST (descriptive, `grid_test.csv`): all 24 configurations are below SPY, from -0.20 to -1.39 pts/yr.
- **How much depends on 2008 and 2020.** The frozen rule was +0.5 pts better than SPY in 2008 and +0.2 pts in 2020, and slightly worse
  in nearly every other year, typically by 0.3-0.6 pts (`yearly_test.csv`). Taking out 2008 and 2020 widens its gap from -0.20 to -0.30 pts/yr. For
  the canonical config, those two years are worth about +0.4 pts/yr (-0.94 becomes -1.34 without them); 2008 gave +1.7 pts and 2020 +1.4 pts.
  For the real VXTH index the dependence is extreme: 2020 alone was +95 pts over the S&P, and without 2008 and 2020 it lags by
  7.2 pts/yr.
- Yearly table, frozen rule minus SPY (pts):

  | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | +0.5 | -0.4 | -0.3 | -0.1 | -0.4 | -0.6 | -0.3 | +0.2 | -0.5 | -0.6 | +0.5 | -0.6 | +0.2 | -0.4 | -0.1 | -0.6 | -0.4 | -0.4 | -0.3 |

## Why the barbell fails, and the hindsight bound
- If held through the crash, the model puts do explode. A 30%-OTM April-2020 put bought on 2020-02-03 was worth 63x its cost on
  2020-03-16, and a 30%-OTM November-2008 put bought on 2008-09-02 was worth 79x on 2008-10-10 and 168x on 2008-11-20. The model does not suppress crash
  convexity. But those payoffs arrive only if the tranche is alive, deep enough and still held at the bottom.
  - A monthly roll caps each tranche's life at one month.
  - A 5x monetization rule cashes out early: the canonical config sold at about 6x on 2020-02-28.
  - Re-striking after the spike buys expensive puts far below the market.
- **Wider rule family, run after TEST** (`grid2_ladder.py`, flagged as tainted). Overlapping tranches held to about expiry and a 20x monetize
  multiple, 48 configurations in all: **0 of 48 beat SPY on DEV, and 0 of 48 on TEST.** Holding to expiry mostly adds bleed: -1.0 to -3.4
  pts/yr at 3.3%/yr.
- **Perfect-hindsight bound** (`oracle_bound.py`; not a strategy). At a 3.3%/yr budget, each tranche is sold at the best model bid of its life:
  +4.2 to +5.2 pts/yr on DEV and +7.0 to +8.3 on TEST. Part of that is simply picking the maximum of noisy daily marks: the within-month
  oracle is also +2 to +3 pts in DEV, where the real rule loses 1.6-1.9. **Even perfect timing does not reach +20.**
- The shortfall of the barbell vs SPY is almost exactly the net premium bleed. The market prices these puts richly enough (SKEW)
  that the crash gains, monetized by any rule you could state in advance, only repay the premium in the two big crashes.

## Required report items
- **After costs vs SPY:** DEV -0.24 (2x: -0.28), TEST -0.20 (2x: -0.24; SSVI: -0.22). The benchmark is 100% SPY total return with its 9.45 bp fee.
- **Max drawdown:** -47.0% on DEV and -51.4% on TEST, vs SPY -47.5% and -51.9%. The tiny premium does not protect against drawdowns.
- **Independent bets:** 216 (DEV) and 225 (TEST) monthly tranches, plus 5 and 8 monetizations. But the payoff depends on about 10
  crash episodes (1990, 1998, 2001, 2002, 2008, 2011, 2015, 2018, 2020, 2025), so the effective sample is tiny.
- **Costs modeled:**
  - Option half-spread: 2.5% of premium (base), 5% (2x), or at least 0.05 points with an ask of at least 0.10 points (tick case).
  - SSVI pricing, which is 1.3-1.7x more expensive in the wings.
  - 1 bp on SPY flows. Commissions (about $0.65 per contract on puts costing $500 or more) are negligible.
- **Survivorship:** not applicable. The instruments are indices, SPY and SPX options.
- **Capacity:** not binding. SPX puts trade millions of contracts a day, and a 1%/yr budget on $1B is about $0.8M of premium a month.
  At present index levels, one 30%-OTM 4-month contract costs about $1-3k, so the rule needs roughly $1M or more of NAV for whole contracts.
- **Artifacts hunted:**
  1. SKEW-noise marks. Found and fixed with the 21-day mean. The raw version flatters the result by 0.06 pts.
  2. Sub-tick 1990s prices (tick case: -0.14 pts on DEV).
  3. Stale-signal monetization: one-day lag enforced.
  4. The wing price level: checked against a real chain and against PPUT, with SSVI as the stress case.
  5. Hindsight-bound decomposition.
  6. The structure of the 1990s proxy term curve.
- **Trading it live** would need an options-enabled account (long SPX puts need no margin), monthly execution near the close
  with limit orders inside the spread, and a rule for strikes that are not listed. That last point matters for 1990s-style low index
  levels, not today. **It is not worth doing to beat SPY.** At best the barbell is insurance that costs about 0.2-1% a year and barely changes
  maximum drawdown at these budgets.

## Files
- **Code:** `prep_data.py`, `pricing.py`, `linz_calib.py`, `calibrate_surface.py` (with the `[PEXP] [SKEW_WIN]` options),
  `calibrate_ssvi.py`, `backtest.py`, `grid_dev.py`, `evaluate.py`, `grid2_ladder.py` (post-test), `oracle_bound.py`,
  `pput_check.py`, `crosscheck.py`, `chain_check*.py`.
- **Results:** `grid_dev.csv`, `bench_dev.csv`, `eval_{dev,test}.csv`, `yearly_{dev,test}.csv`, `excl_{dev,test}.csv`,
  `trades*_{dev,test}.csv`, `daily_{dev,test}.csv.gz`, `grid_test.csv`, `grid2_ladder.csv`, `oracle_bound.csv`,
  `pput_check.txt`, `pput_check_yearly.csv`, `crosscheck.csv`, `crosscheck_yearly.csv`, `chain_check_linz_s21.csv`.
- **Pre-registration:** `PREREG.md` and `frozen_config.json`.
- **Data:** `data/round5/m04_tail_barbell/`: `panel.pkl` and `surface{,_s21}.pkl` / `surface_ssvi{,_s21}.pkl`, rebuilt by the calibration scripts
  (about 6-10 minutes each on one core).
