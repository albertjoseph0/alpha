# m07: favourite-longshot harvest on Kalshi and Polymarket

**Verdict: NO EDGE** on both venues. The Polymarket DEV edge (+2.2% per bet) did not survive the sealed TEST period
(+0.26% per bet, CI -2.2% to +2.6%), and it turns negative at 2x costs. Kalshi favourites were overpriced after fees
in every DEV cell and again in TEST. Capacity is also tiny, so even the DEV version could not beat SPY at a
realistic account size.

## Idea and frozen rules (see PREREG.md)
Favourites (priced 85-97c) on event contracts are said to win more often than their price implies. The strategy is
long-only: buy the leading side, hold to resolution, and the loss is capped at the premium.

* **Primary (Polymarket):** 72h before the scheduled `endDate`, pick the leading outcome from the hourly bar ending at d-1h. Buy it
  if its price at d is in [0.85, 0.97]. The cost is price + 1c of slippage plus a taker fee of 0.05*p*(1-p), which is
  conservative because Polymarket charged 0 before 2025. One unit of capital per event.
* **Secondary (Kalshi):** 1h before the scheduled close, buy the leading side at the real ask if the ask is in [0.95, 0.97].
  The cost is ask + 0.5c plus the fee ceil(0.07*C*P*(1-P))/C with C = 100. This was the "least bad" DEV cell.
* 2x costs: slippage and fees doubled (Kalshi also pays another half-spread).

## Results (after costs; bets are event-level; CIs are 95% event-cluster bootstrap)
| | Polymarket DEV (22-10..24-07) | **Polymarket TEST (24-07..26-09)** | Kalshi DEV (21-07..24-07) | Kalshi TEST (24-07..26-07) |
|---|---|---|---|---|
| event bets | 464 | **485** | 286 | 38 (255 without filters) |
| mean price / win rate | 92.7% / 96.0% | **91.8% / 93.4%** | 96.1% / 96.3% | 96.1% / 94.7% |
| edge per contract after fees | +2.02c (0.34, 3.64) | **+0.24c (-2.00, +2.35)** | -0.51c (-2.78, +1.45) | -2.06c (-9.96, +3.28) |
| return per $ staked | +2.18% (0.31, 3.95) | **+0.26% (-2.17, +2.56)** | -0.52% (-2.87, +1.50) | -2.13% (-10.3, +3.4) |
| fee per contract / median hold | 0.29c / 4.3 d | 0.33c / 3.2 d | 0.24c / 0.26 d | 0.24c / 0.06 d |
| return per $ at 2x costs | +0.88% (-0.97, +2.63) | **-1.06% (-3.46, +1.20)** | -2.73% (-5.03, -0.75) | -4.23% |
| CAGR, sim f=5%/event, sample opportunities (maxDD) | 23.5% (-12%) | **1.8% (-29%)** | -3.0% (-22%) | -2.1% (-9%) |
| same at 2x costs | 5.5% (-19%) | **-11.9% (-39%)** | -12.8% (-36%) | -4.0% (-9%) |
| capacity-limited annual return, K=$100k (PREREG metric b) | 2.7% | 26.9%* | -0.3% | -11.9% |
| SPY CAGR, same window | 29.3% | **18.0%** | 9.5% | 17.7% |

\*The TEST value of 26.9% equals the fully deployed rate of a +0.26% mean with a 3-day hold. Its CI includes zero, so the PREREG's
first condition (CI lower bound > 0) fails and metric (b) is not meaningful. At 2x costs it is -110%/yr.

Other TEST checks for Polymarket: 2025 had ret -6.3% (n=48) and 2026 had +0.9% (n=433). Markets with lifetime volume >= $10k
had ret -2.9% (n=91), so the small positive mean comes from the tiniest markets. Holding only one market per event gives +0.24%.
Unclean resolutions do not change anything.

**Calibration** (`out/calib_frozenH.csv`, `out/calib_DEV_TEST.png`, `out/calib_DEV.png`): in the 85-97c band, Polymarket
favourites win 1-2 pts more than the hourly mid/last price in TEST (e.g. 0.917 -> 0.940 and 0.961 -> 0.982, CIs about +/-4-5 pts).
A 1c slippage plus a ~0.3c fee roughly cancels that. On Kalshi the favourite wins at about its ask price (0.966 -> 0.967 in DEV).
The only large Kalshi deviation (favourite at a 98.7c ask wins only 93.7%) comes from books with a spread > 20c, where the 99c ask is not a real
price. With spreads <= 5c the favourite wins 99%, matching the price. On Kalshi, 0 of about 110 DEV grid cells (H x price band)
had positive mean P&L after fees. On Polymarket 41% did, but only 3% had CI > 0, so the DEV "winner" was a multiple-testing pick.

## Capacity
Capacity per market = 10% of its average daily $ volume, which uses lifetime volume and so flatters capacity.
* Polymarket DEV: only about $1.7k of capital could be kept deployed on average, which is about $3k/yr of profit at full capacity.
  That is why the +2.2%/bet edge gives just 2.7%/yr at K=$100k and 0.3% at $1M.
* Polymarket TEST: 1.15M eligible markets. The median qualifying market can absorb **$4**, the mean $418. Scaled to the
  universe, about $200k could be deployed on average, but the capacity-weighted P&L is negative (the big markets lost).
* Kalshi: about $90 (DEV) and $208 (TEST) of capital deployable on average in the qualifying sample markets.

## Artifacts hunted
1. **Kalshi early-close lookahead:** 92% of markets can close early, and the close time moves when the event resolves.
   Anchoring at the actual close_time would be lookahead. The primary universe keeps on-schedule closes that were seen on the
   tape before the decision. Off-schedule closes in TEST lose -6.6%/bet (-6.4c per contract, CI -10.6c to -2.5c) (favourites lose when a market closes early),
   so excluding them flatters the favourite. Kalshi is negative even so.
2. **Fake asks in empty books** (above). Near-certain Kalshi favourites look overpriced there, but the longshot side's ask in those
   books is about 65c, so there is nothing to harvest.
3. **Multiple testing:** the Polymarket DEV pick was the best of about 110 cells, and TEST shrank it by about 90%.
4. **Outcome-based filters:** DEV dropped unclean Polymarket resolutions. The TEST primary pays them as reported, with no change.
5. **Price quality:** Polymarket history is an hourly mid/last price, not an executable ask. In $4-capacity markets the real spread is
   probably wider than 2c, so even the small TEST mean is optimistic.
6. **Survivorship:** none from current lists. Polymarket is enumerated from the gamma API, which includes all closed markets. Kalshi
   markets come from random-time trade-tape sampling of settled markets (markets that never traded cannot be bought anyway).
   The TEST samples are seeded and outcome-blind: Polymarket 5,000 of 1.15M markets (seed 20260924) and Kalshi 6,000 markets from a
   35% event sample. Kalshi DEV used 10,133 of 20,423 sampled markets (a random prefix of a seeded shuffle).

## Trading it live (not recommended)
You would need a Kalshi account (US) or a Polymarket wallet with USDC on Polygon (a non-US venue, or Polymarket US), plus API order
placement at d = scheduled close - H. Resting limit orders (maker) instead of taking would remove the fee and half the spread.
That is the only variant that might leave a small positive edge, and it has not been tested here (no historical order books).
Expected size is hundreds to low thousands of dollars.

## Files
Scripts run in order: k02 -> k03 -> k05 -> k04 (Kalshi), p01 -> p02/p03 (Polymarket), a01 (snapshots), a02 (DEV grid),
a03 (frozen evaluation), a04 (calibration). lib_fl.py holds costs, sizing and the simulation. Outputs are in `out/`
(`eval_*_{DEV,TEST}_frozen.txt`, `grid_*_DEV.csv`, `calib_*`). Data is in `data/round5/m07_prediction_markets/`.
