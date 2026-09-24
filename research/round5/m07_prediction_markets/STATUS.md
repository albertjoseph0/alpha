# m07 prediction markets: favourite-longshot harvest (STATUS)

Last update: 2026-09-24 (round 5b, resumed instance)

## Pipeline (scripts in this folder, data in data/round5/m07_prediction_markets/)
| step | script | output | state |
|---|---|---|---|
| Kalshi discovery (tape sampling, 500 random times/period) | k02_discover.py | kalshi_discovery.csv.gz | DONE (DEV 21,259 / TEST 64,530 tickers) |
| Kalshi metadata | k03_meta.py DEV/TEST | kalshi_meta_<P>.csv.gz | DEV done; TEST queued after p01 TEST |
| Kalshi sample | k05_build.py DEV | kalshi_sample_DEV.csv.gz | DEV done (20,423 mkts, 6,119 events) |
| Kalshi hourly candles (8d before close) | k04_candles.py DEV | kalshi_candles_DEV.pkl.gz (resumable) | DEV running (~2h) |
| Polymarket enumeration (keyset) | p01_enum_markets.py a b | poly_markets_<a>_<b>.csv.gz, poly_parts/ | DEV done (11,261); TEST running |
| Polymarket hourly prices | p02_prices.py DEV | poly_sample_DEV, poly_hist_DEV.pkl.gz (resumable) | DEV running (6,825 mkts) |
| snapshots | a01_snapshots.py DEV | snap_kalshi_DEV / snap_poly_DEV | works (tested on partial data) |
| DEV analysis | a02_dev.py (uses lib_fl.py) | out/*.csv, out/calib_DEV.png, out/artifacts_DEV.txt | works (partial data) |

k01 (enumerate all events) was abandoned after 8 series and is not needed.
Bug fixed 2026-09-24: pandas datetime64[us] -> epoch conversion (was //1e9 on microseconds).

## Design decisions
* Kalshi anchor = close_time. `can_close_early` is True for 92% of DEV markets, but recurring series close on a
  clock schedule; primary universe = on-schedule closes (local close HH:MM = series mode) & seen on the tape
  (random sampling time) <= decision time.  Off-schedule closes = potential early close = lookahead, excluded.
* Polymarket anchor = endDate (scheduled; median resolution 28h after); skip if closedTime <= decision.
* Signal bar = last hourly bar <= d-1h (which side leads); execution = bar <= d at the ask (Kalshi) or
  price+1c (Polymarket). One unit of capital per event, split equally over its qualifying markets.
* Fees: Kalshi ceil_to_cent(0.07*C*P*(1-P)) per order (C=100), no settlement fee; Polymarket 0.05*p*(1-p)
  (2026 category schedule; 0 historically). 2x costs = 2x fee + 2x slippage + extra half-spread.

## Early (partial-data, ~4% of DEV) impressions
No DEV grid cell had a mean-pnl CI excluding zero; favourites look roughly fairly priced after fees.

## Next steps
1. wait for k04 DEV + p02 DEV to finish; rerun a01 DEV, a02_dev.py; pick frozen rule; write PREREG.md.
2. TEST: k05_build TEST -> event-subsample (seeded, pre-registered) -> k04 TEST; p02 TEST (seeded subsample);
   a01 TEST; a03_test.py once.
3. README.md with report + verdict.
