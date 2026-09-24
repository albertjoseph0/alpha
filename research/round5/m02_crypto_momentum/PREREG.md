# PREREG: m02 crypto cross-sectional momentum + BTC trend filter

Written 2026-09-24 after the DEV study (dev_results.txt, dev2_results.txt) and **before** any backtest
touches 2022+ data. The TEST is run once with `run_test.py`; results are reported as they come out.

## Frozen rule (= `backtest.DEFAULT`, declared before the first DEV backtest; unchanged after DEV)
- Data: Binance spot daily klines (UTC), all *USDT pairs from data.binance.vision incl. delisted pairs.
  Excluded: stablecoins/fiat/gold tokens, leveraged tokens (*UP/*DOWN/*BULL/*BEAR, BULL, BEAR),
  wrapped duplicates (WBTC, WBETH, BETH), tokenized SPY (SPYB). Token redenominations are back-adjusted (prep.py).
  A symbol with a >7 day gap is split into separate instruments (e.g. LUNA classic vs LUNA 2.0).
- Signal every Sunday close t, using data <= t only:
  - Eligible: listed at t, >= 60 days of history, finite 28-day momentum.
  - Universe: top 30 by trailing 30-day mean USDT quote volume (days <= t).
  - Hold the 5 coins with the highest 28-day return (close_t / close_{t-28} - 1), equal weight.
  - BTC filter: if BTC close_t <= SMA100(BTC)_t, hold 100% USDT (earns 0).
- Execution at the close of t+1 (Monday), i.e. a one-bar lag; new weights earn from t+2 onward.
  Positions are rebalanced back to equal weight every week.
- Delisting: an instrument whose data ends while held is (a) sold at its last close, paying costs, or
  (b) written off to zero. Both are reported.

## Costs (per side, as a fraction of traded value)
- Taker fee 10 bp.
- Spread + slippage s(ADV) = clip(3 + 30/sqrt(ADV in $M), 3, 150) bp, where ADV is the trailing 30-day
  mean Binance quote volume at the signal day ($1B ADV -> 4 bp; $100M -> 6 bp; $10M -> 12.5 bp;
  $1M -> 33 bp; $40k -> 150 bp cap).
- Primary result at 1x; also reported at 2x (all cost components doubled).
- Capacity: add square-root impact 1.0 x sigma_daily(60d) x sqrt(order $/ADV $).

## Test period and benchmarks
- TEST: 2022-01-01 -> 2026-08-31 (last complete month in the Binance monthly archive).
- Primary benchmark: BTC buy & hold (BTCUSDT close). Secondary: SPY buy & hold (total return, adjusted close).
- Controls (for interpretation, not the verdict): BTC with the same SMA100 filter; EW top-30 with the filter.

## Success criterion (decided now)
- `MOONSHOT CANDIDATE`: TEST CAGR at 1x costs, delist->last, >= BTC buy & hold CAGR + 20 pts, AND still
  > BTC buy & hold at 2x costs with delist->zero.
- `REAL BUT SMALLER`: beats BTC buy & hold at both 1x and at (2x costs, delist->zero), but by < 20 pts.
- `NO EDGE`: otherwise.
- I will also say whether it beats the BTC+SMA100 control. If it does not, the momentum selection adds
  nothing over a plain BTC trend filter, and any edge belongs to the filter.

## What DEV already suggests (to hold myself to account)
DEV 2018-2021: 68.1% vs BTC 36.4% (+31.7), 59.5% at 2x costs. But the weekly excess has t = 0.58; it
is negative without the best 5 weeks; DEV ex-2021 is 20.1% vs BTC 29.3%; and the BTC+SMA100 control
alone makes 44.3% ex-2021. Neighbouring parameter choices swing DEV CAGR from 20% to 113%. My prior
is that the TEST will not clear +20 pts.
