# m02: Crypto cross-sectional momentum with a BTC trend filter. Verdict: **NO EDGE**

**Idea.** Every week, hold the 5 coins with the best 28-day return among the 30 most liquid Binance
USDT spot pairs. When BTC is below its 100-day SMA, hold USDT instead. The evidence cited was
Liu, Tsyvinski & Wu (2022). The target was BTC buy & hold + 20 pts/yr after costs.

**Result.** In DEV (2018-2021) the strategy beat BTC by 32 pts/yr. All of that came from the 2021 mania.
In the sealed TEST (2022-01 to 2026-08) it made **-41.9%/yr**, while BTC made +11.3% and SPY +12.2%.
In TEST, the cross-sectional momentum signal among liquid coins reverses: the top-5 momentum coins
underperform the liquid universe by 0.97%/week (t = -2.2). No bug or data artifact explains this.
The loss comes from the signal, not from costs.

## Data and universe (point-in-time, survivorship-free)
- Source: Binance public archive `data.binance.vision`, monthly 1d spot klines for **all 735 *USDT
  pairs ever listed**, including delisted ones (`fetch.py`; 122 identical files reused read-only from
  m09 via `import_m09.py`). The data runs from 2017-08-17 to **2026-08-31**, the last complete archive month.
- Both named delistings are in the data: LUNAUSDT (Terra Classic, last bar 2022-05-13 at $0.00005)
  and FTTUSDT (last bar 2022-11-15). A symbol with a gap longer than 7 days is split into separate
  instruments, so LUNA 2.0 (from 2022-05-31) is a new coin. There are 660 instruments in total, and
  196 of them ended before the data end.
- Excluded (`prep.py`, list in `prep_output.txt`):
  - 26 stablecoin, fiat and gold bases, plus KGST and U, which a volatility scan flagged as stablecoins.
  - 48 *UP/*DOWN/*BULL/*BEAR leveraged tokens, plus the stand-alone BULL and BEAR tokens.
  - WBTC, WBETH and BETH, which duplicate BTC and ETH.
  - SPYB, a tokenized SPY.
- Token redenominations were detected (a one-day price ratio of more than 50x that is within 0.3 of a
  power of ten) and back-adjusted: COCOS, DREP, SUN, BNX and QUICK. Without this, COCOS shows a fake
  +129,000% day. Real crashes such as LUNA are left untouched.
- Liquidity rank = trailing 30-day mean USDT quote volume, using days up to and including the signal
  day. Coins also need at least 60 days of history.
- **Limitation:** Binance had only 6-19 USDT pairs in 2018, so in 2018 the "top 30" is the whole
  market. From 2019 on there are more than 30 pairs.

## Rule, timing and costs (frozen in `PREREG.md`; code in `backtest.py`)
- **Timing.** The signal is taken at the Sunday close (UTC) and executed at the Monday close, a
  one-bar lag. The new weights earn from Tuesday on. Positions go back to equal weight every week.
  USDT earns 0.
- **Costs per side.** A 10 bp taker fee, plus spread and slippage of
  `clip(3 + 30/sqrt(ADV $M), 3, 150)` bp, where ADV is the trailing 30-day Binance quote volume.
  Examples: 4 bp at $1B ADV, 12.5 bp at $10M and 33 bp at $1M. Results are also shown at 2x
  (everything doubled).
- **Capacity model.** The cost above plus a square-root impact of `1.0 x sigma_d x sqrt(order/ADV)`.
- **Delisting.** A held coin whose data stops is either sold at its last close or valued at zero.
  Both are reported.

## Results

### DEV 2018-01-01 → 2021-12-31 (`dev_results.txt`, `dev2_results.txt`)

| Strategy | CAGR | vs BTC | vs SPY | MaxDD | Trades |
|---|---|---|---|---|---|
| BTC buy & hold | 36.4% | – | +19.1 | -81% | – |
| SPY buy & hold | 17.3% | -19.1 | – | -34% | – |
| **Canonical, 1x costs** | **68.1%** | **+31.7** | +50.8 | -75% | 799 |
| Canonical, 2x costs | 59.5% | +23.1 | +42.2 | -75% | 799 |
| Canonical, delisted → 0 | 68.1% | +31.7 | +50.8 | -75% | 799 (0 delisting hits) |
| Control: BTC + same SMA100 filter | 46.7% | +10.3 | +29.4 | -73% | 36 |
| Control: EW top-30 + filter | 57.3% | +20.9 | +40.0 | -73% | 3514 |

**DEV excluding the 2021 mania (2018-2020):** canonical 20.1% (2x costs 14.0%), BTC 29.3%, SPY 13.8%,
BTC + filter 44.3%. Excluding 2021, the strategy **lost to BTC by 9 pts** and to the plain BTC trend
filter by 24 pts.

Calendar years, canonical vs BTC: 2018 -62.8 vs -72.3; 2019 +30.2 vs +94.3; 2020 +257 vs +302;
2021 +360 vs +60.

Warning signs that were already visible in DEV (recorded in PREREG before the TEST):
- The weekly excess over BTC had t = 0.58, and it turned negative once the best 5 weeks were removed.
- The cross-sectional spread (top-5 momentum minus top-30 EW, next week) was +0.61%/wk with t = 0.75,
  and the rank IC was about 0.
- The result was very sensitive to arbitrary choices:
  - Changing the universe to the top 20 gave 20% CAGR; changing it to the top 50 gave 63%.
  - Ranking liquidity by median rather than mean volume gave 113%.
  - Across the 60-cell parameter grid (`dev_grid.csv`), CAGR ran from -5% to +116%.
- The 2021 gains came from LUNA, MATIC, CHZ, SUSHI and SAND (`dev_attribution.csv`).

### TEST 2022-01-01 → 2026-08-31, run once after PREREG (`test_results.txt`)

| Strategy | CAGR | vs BTC | vs SPY | MaxDD | Trades |
|---|---|---|---|---|---|
| BTC buy & hold | 11.3% | – | -0.9 | -67% | – |
| SPY buy & hold | 12.2% | +0.9 | – | -25% | – |
| **Canonical, 1x costs, delist → last price** | **-41.9%** | **-53.2** | **-54.1** | **-93%** | 887 |
| Canonical, 2x costs | -44.5% | -55.8 | -56.7 | -94% | 887 |
| Canonical, delist → 0 (1x / 2x) | -41.9% / -44.5% | -53.2 / -55.8 | | -93% / -94% | 0 delisting hits |
| Control: BTC + SMA100 filter | 4.4% | -6.9 | -7.8 | -43% | 46 |
| Control: EW top-30 + filter | -31.9% | -43.2 | -44.1 | -85% | 4217 (2 delisting hits) |

The strategy lost money in every calendar year: 2022 -48.0%, 2023 -45.7% (BTC +156%), 2024 -26.5%
(BTC +121%), 2025 -49.6% and 2026 YTD -23.9%. It was invested in 49% of weeks.

The two delisting treatments give identical results because the rule never held LUNA or FTT when
they collapsed. In May 2022 the BTC filter had already moved it to cash. In the FTX week (from
2022-11-07) it was invested, but FTT was not among the top-5 momentum coins. Only the EW control,
which holds the whole top 30 and does no momentum selection, was hit.

**Independent bets.** There were about 243 weekly rebalances in TEST (about 120 of them invested)
and about 209 in DEV (about 113 invested), with 5 coins each. These are highly correlated bets.

**Capacity.** In DEV, CAGR fell from 68% to 57% at $100k, 39% at $1M, 7% at $10M and -10% at $30M.
In TEST it was -42% at $0 and -46% at $1M. Even in DEV, the edge was gone above roughly $1-5M.
Binance USDT volume understates total market liquidity, but the coins this rule picks are mostly
thin mid-caps.

## Artifact hunt: what I looked for and what I found
1. **Data or bookkeeping bug behind the -42% TEST.** Checked:
   - Year-end prices of BTC, ETH, SOL, XRP, DOGE and BNB match known values.
   - There are no duplicate bars.
   - The worst portfolio days are real events. On 2023-11-11, GAS fell 52% in a pump-and-dump. On
     2023-06-10, during the SEC "securities" alt dump, LINA, ARPA, KEY, RNDR and LDO fell 12-21%.
     On 2023-02-09 came the Kraken staking crackdown.
   - Costs explain only 2.6 pts/yr (the gap between the 1x and 2x results).

   Finding: this is a real loss, not a bug.
2. **Does the signal itself work? (`run_test_diag.py`, `xs_momentum_check.csv`)** Ignoring the filter,
   the top-5 momentum coins minus the liquid universe returned -0.97%/week in TEST (t = -2.17), and the
   mean rank IC was -0.013. Among liquid Binance coins in 2022-26, 1-4 week momentum picks recent
   pumps (GAS, TRB, BOND, LINA, KEY, BONK, FLOKI, LAYER), which then mean-revert. Newly listed launchpool
   tokens enter the liquidity top 30 at peak volume and then decline. The DEV "momentum" was never
   statistically distinguishable from zero.
3. **2021 mania dependence.** Confirmed. Excluding 2021, DEV loses to BTC.
4. **The trend filter as the real source of return.** In DEV, the filter alone applied to BTC made
   44% (ex-2021), which is more than momentum. In TEST it made 4.4% vs BTC's 11.3%, so it did not
   beat buy & hold either.
5. **Survivorship.** Handled with the full point-in-time archive, including delisted pairs. The rule
   happened to have zero delisting exposure, so the zero-value case costs nothing here.
6. **Lookahead.** Signals use closes up to and including day t, execution is at t+1, and the liquidity
   rank uses trailing data. Redenomination adjustment rescales earlier prices by an exact power of ten,
   which does not change any return or ranking except on the redenomination day.

## Verdict: **NO EDGE**
In the sealed TEST, the strategy trails BTC by 53 pts/yr at 1x costs and 56 pts at 2x, and it trails
SPY by 54 pts/yr. The DEV outperformance was a 2021-mania effect on top of a statistically zero
signal. In liquid crypto after 2021, short-horizon cross-sectional momentum has the wrong sign. This
matches the brief's lesson that fancy signals collapse to trend filters plus noise. Liu, Tsyvinski
& Wu's sample (2014-2018, including small coins) does not carry over to a tradeable liquid universe
in 2022-26.

**What trading it live would take (not recommended):**
- A Binance spot account (or a US equivalent with far fewer listings).
- Weekly Monday-close rebalancing through taker orders.
- About 26x annual turnover.
- Capacity under about $1-5M.

It would have lost about 90% of capital in TEST.

## Files
- Code: `fetch.py`, `import_m09.py`, `prep.py`, `backtest.py`, `run_dev.py`, `run_dev2.py`,
  `run_test.py`, `run_test_diag.py`.
- Outputs:
  - Setup: `PREREG.md`, `prep_output.txt`.
  - DEV: `dev_results.txt`, `dev2_results.txt`, `dev_grid.csv`, `dev_curves.csv`, `dev_attribution.csv`.
  - TEST: `test_results.txt`, `test_results.csv`, `test_curves.csv`, `test_diag.txt`,
    `test_attribution.csv`, `xs_momentum_check.csv`.
  - `STATUS.md`.
- Data: `data/round5/m02_crypto_momentum/`:
  - `klines_1d.parquet`
  - `close.parquet`, `qv.parquet` and `trades.parquet`
  - `instruments.csv`
  - `raw/`: kept, because m09 reads it.
