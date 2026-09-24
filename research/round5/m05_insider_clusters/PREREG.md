# m05 insider clusters: PRE-REGISTRATION (frozen 2026-09-24, before any TEST-period number was computed)

DEV = events filed 2006-01-01 .. 2015-12-31 (all development so far: `dev_results/`).
TEST = events filed 2016-01-01 .. 2026-03-31 (last SEC quarterly insider data set), with prices through 2026-09-23.
The test is run once with `python 09_test.py test` and reported as it comes out.

## Event (unchanged from DEV, `03b_build_events.py`)
Form 4 open-market purchases (code P, non-derivative, common stock, shares > 0, price > 0) by officers or
directors. On each SEC filing date F of an issuer: count distinct insiders with a purchase whose
transaction date is in [F-30d, F] and that was filed on or before F. The first F with 3 or more insiders is an event,
followed by a 182-day cooldown per issuer. **Entry is at the close of the first trading day strictly after F**, and
all filters use data up to the close of F.

## Universe (price and liquidity at the close of F)
The name has a yfinance price that matches the insiders' reported VWAP within 0.75-1.33x, price >= $2,
60-day median dollar volume >= $100k, and market cap <= $10B (SEC shares outstanding lagged 20 days).

## Frozen rules (hold H = 126 trading days, equal weight at entry, positions drift, fully invested when any position is open, 0% on idle cash)
* **A (rules baseline, Cohen-Malloy-Pomorski):** event with at least 3 *opportunistic* insiders (`n_opp >= 3`). An insider is routine
  if they traded the issuer in the same calendar month in each of the 3 prior years.
* **A+B (Jev):** A **and** at least 3 insiders who have at least one purchase that Jev (agent m05) does *not* classify as a
  non-discretionary purchase (offering, private placement, plan or DRIP, or a 10b5-1 plan, each at probability 0.5 or higher, or the
  AFF10B5ONE flag). Filter name: `B:jev_clean>=3 & opp`.
* References (not candidates): `base` (all events) and `dict:kw_clean>=3 & opp` (the same filter with keyword or
  Loughran-McDonald dictionary flags instead of Jev).
* Secondary: logistic regression (C=0.1, standardized, 1-99% clipped) trained on every DEV event whose exit is before
  2016-01-01, with features A, A+Jev and A+dict. Buy the top tercile, where the threshold is the 2/3 quantile of in-sample DEV scores.

## Costs (round trip, applied half at entry and half at exit, and on rebalancing trades)
300 bp if the price is under $5. Otherwise the worse of the market-cap bucket and the ADV bucket: microcap (under $300M, or ADV under $1M) 200 bp, small cap
($300M-$2B, or ADV $1M-$10M) 80 bp, mid cap 30 bp. Results are also reported at 2x and 0x costs.

## Survivorship
Only about 25% of events have yfinance prices, because delisted tickers are missing. The missing events (vwap >= $2 and passing the same SEC-data
filters, subsampled at the observed universe pass rate) are added with a flat path and a terminal return of -50% or -100%,
and also 0% for information. All three are reported.

## Benchmarks and success criterion
CAGR of SPY and IWM (adjusted close) over the same calendar window as the strategy equity curve.
* `MOONSHOT CANDIDATE`: A or A+B TEST CAGR at 1x costs is at least 20 points above both SPY and IWM, **and** it still beats IWM
  with missing names at -50%.
* `REAL BUT SMALLER`: A or A+B TEST CAGR beats both SPY and IWM at 1x **and** 2x costs, and the event-level mean
  excess return vs IWM has t > 2, but the -50% survivorship bound is not required.
* Otherwise `NO EDGE`.
* Jev adds value only if A+B beats A in TEST by at least 1 point of CAGR **and** the Jev ML model beats both the A-only model and the dict model in
  TEST AUC.

## DEV numbers at freeze (H=126, 1x costs)
A 7.5% (2x 2.1%, -50% bound -56.7%), A+B 7.5% (1.9%, -56.7%), base 6.6%, dict 7.6%, SPY 6.8%, IWM 6.3%.
DEV already shows no moonshot. The test is run to measure how large any real residual edge is.
