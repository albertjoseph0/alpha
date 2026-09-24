"""Stage 4 (Kalshi): hourly candlesticks (yes bid/ask OHLC, trade price, volume) for the 8 days before
each sampled market's anchor time.

usage: k04_candles.py DEV|TEST  [max_markets]
Input : kalshi_sample_<PERIOD>.csv.gz (ticker, anchor_ts) written by k05_build.py --select
Output: kalshi_candles_<PERIOD>.pkl.gz  dict ticker -> np.ndarray [n, 7]
        columns: end_ts, yes_bid_close, yes_ask_close, price_close, volume, yes_ask_low, yes_bid_high
"""
import gzip
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

B = "https://api.elections.kalshi.com/trade-api/v2"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
samp = pd.read_csv(os.path.join(D, f"kalshi_sample_{per}.csv.gz")).head(cap)
OUT = os.path.join(D, f"kalshi_candles_{per}.pkl.gz")
res = {}
if os.path.exists(OUT):
    with gzip.open(OUT, "rb") as f:
        res = pickle.load(f)


def f(x):
    return np.nan if x is None else float(x)


for i, r in enumerate(samp.itertuples()):
    if r.ticker in res:
        continue
    start = int(max(r.anchor_ts - 8 * 86400, r.open_ts))
    end = int(r.anchor_ts)
    path = "/historical/markets/%s/candlesticks" if r.archived else "/markets/%s/candlesticks"
    if not r.archived:
        # live endpoint needs the series ticker
        path = "/series/%s/markets/%%s/candlesticks" % r.series
    d = get(B + path % r.ticker, dict(start_ts=start, end_ts=end, period_interval=60))
    cs = d.get("candlesticks", []) or []
    arr = np.array([[c["end_period_ts"], f(c["yes_bid"].get("close")), f(c["yes_ask"].get("close")),
                     f((c.get("price") or {}).get("close")), f(c.get("volume")),
                     f(c["yes_ask"].get("low")), f(c["yes_bid"].get("high"))] for c in cs]) if cs else np.zeros((0, 7))
    res[r.ticker] = arr
    if i % 250 == 0:
        print(i, len(samp), flush=True)
        with gzip.open(OUT, "wb") as fo:
            pickle.dump(res, fo)
with gzip.open(OUT, "wb") as fo:
    pickle.dump(res, fo)
print("done", len(res))
