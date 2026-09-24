# m07 PREREG: favourite-longshot harvest on Polymarket (primary) and Kalshi (secondary)

Written 2026-09-24, after DEV analysis (`a02_dev.py`, `out/artifacts_DEV.txt`) and before any TEST outcome was looked at.
TEST data was downloaded blind: sample selection uses no outcome field, and no TEST snapshot, calibration or
P&L has been computed. Everything below is frozen.

## Periods
* DEV: Kalshi 2021-07-15 to 2024-07-01; Polymarket CLOB 2022-10-01 to 2024-07-01 (settlement date).
* TEST: 2024-07-01 to 2026-09-01 for Polymarket and 2024-07-01 to 2026-07-20 for Kalshi (the archive end).

## Frozen rule: primary (Polymarket)
* Anchor = scheduled `endDate`. Decision time d = endDate - **72 h**. Skip the market if `closedTime` <= d.
* Signal: the hourly price bar with end <= d - 1h picks the leading outcome (price >= 0.5).
* Execution: the leading outcome's hourly price at the last bar <= d. Trade only if that price is in **[0.85, 0.97]**.
  Buy it at price + 1c of slippage. Hold to resolution and get the final `outcomePrices` payout (1, 0 or 0.5 void).
* No outcome-based filter in the primary run: unclean resolutions (0/0, 1/1, fractional) are paid as reported.
  The DEV selection used clean resolutions only, and the difference on DEV was 13 of 477 events with ret 0.0222 vs 0.0218.
  The clean-only version is reported alongside as a secondary line.
* Sizing: one unit of capital per event, split equally over that event's qualifying markets.
* Costs (base, k=1): +1c slippage and a taker fee of 0.05*p*(1-p) per contract. Polymarket charged 0 before 2025 and
  only in some categories after that, so this is conservative. 2x costs: +2c and 0.10*p*(1-p).

## Frozen rule: secondary (Kalshi, the DEV "least bad" cell; no DEV cell had positive mean P&L)
* Anchor = scheduled close_time (on-schedule closes only). The market must have been seen on the trade tape at d or earlier.
  d = close - **1 h**. Buy the leading side at the real ask when the ask is in **[0.95, 0.97]**.
* Costs: ask + 0.5c of slippage, plus a fee of ceil_to_cent(0.07*C*P*(1-P))/C with C = 100 contracts. 2x costs double the
  slippage and the fee and add another half-spread.

## TEST samples (seeded, outcome-blind)
* Polymarket: the universe is binary CLOB markets with closedTime in TEST and startDate <= endDate - 73h (the market
  exists at the signal bar). That is 1,151,457 markets in 164,050 events. The sample is **5,000 markets**,
  `DataFrame.sample(n=5000, random_state=20260924)` (`p03_test_sample.py`), a sampling fraction of 0.434%.
* Kalshi: a 35% event sample (seed 20260924, `k05_build.py`) of tape-discovered TEST markets. The first **6,000**
  markets of its seed-7 shuffle are used (`k04_candles.py TEST 6000`).

## Metrics (`a03_eval.py`) and benchmark
* Benchmark: SPY total return CAGR over the same window.
* Per-bet: win rate vs price, edge per contract after fees, and mean return per $ with an event-bootstrap 95% CI.
  Calibration of the leading side by price bin, with CIs.
* Annualized return on capital: (a) fully deployed rate = 365 * sum(ret)/sum(days) (an upper bound);
  (b) **capacity-limited annual return at account size K** = fully deployed rate * min(1, U_K), where
  U_K = [sum over sample bets of cap_i * days_i / sampling fraction] / (K * period days) and
  cap_i = 10% of the market's average daily $ volume. K = $100k is primary; $10k and $1M are also reported.
  (c) the calendar-time simulation on sample opportunities only (f = 5% of equity per event), which is a lower bound.
* Also reported: max drawdown, worst losing streak, per-year and per-category results, and 2x costs.

## Success criterion (applied to the primary rule, base costs)
* **MOONSHOT CANDIDATE**: the mean return per $ has a 95% CI lower bound > 0 **and** (b) at K = $100k >= SPY CAGR + 20 pts.
* **REAL BUT SMALLER**: the CI lower bound is > 0 and (b) at K = $100k > SPY CAGR.
* **NO EDGE**: anything else. That includes a real per-bet edge whose capacity-limited return does not beat SPY.
TEST is run once. Any later rerun will be reported as tainted.
