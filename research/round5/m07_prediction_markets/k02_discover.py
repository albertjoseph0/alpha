"""Stage 2 (Kalshi): discover markets by sampling the public trade tape at random times.

For each of N random timestamps t (uniform over the period), fetch the 1000 most recent trades with
created_time <= t (GET /historical/trades?max_ts=t).  Every non-combo ticker traded in that page is
"discovered at" the time of its latest trade in the page.  A market enters a bet sample later only if
its discovery time is <= the decision time, so the universe uses no future information.

Output: data/round5/m07_prediction_markets/kalshi_discovery.csv.gz
  columns: period, window_t, ticker, disc_ts (latest trade time in the page), n_trades, contracts
"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

B = "https://api.elections.kalshi.com/trade-api/v2"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
OUT = os.path.join(D, "kalshi_discovery.csv.gz")


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


PERIODS = {
    # DEV: markets resolving before 2024-07-01. Kalshi opened July 2021.
    "DEV": (ts("2021-07-15T00:00:00Z"), ts("2024-06-30T00:00:00Z")),
    # TEST: 2024-07-01 .. historical cutoff (2026-07-25).  Sampled now only to build the universe;
    # no prices/outcomes of TEST markets are looked at until PREREG.md is written.
    "TEST": (ts("2024-07-01T00:00:00Z"), ts("2026-07-20T00:00:00Z")),
}
N = {"DEV": 500, "TEST": 500}

rows = []
rng = np.random.default_rng(20260924)
for per, (a, b) in PERIODS.items():
    times = np.sort(rng.integers(a, b, N[per]))
    for i, t in enumerate(times):
        d = get(B + "/historical/trades", dict(max_ts=int(t), limit=1000))
        tr = d.get("trades", [])
        if not tr:
            continue
        df = pd.DataFrame(tr)
        df = df[~df.ticker.str.startswith("KXMVE")]
        if df.empty:
            continue
        df["t"] = df.created_time.map(ts)
        df["c"] = df.count_fp.astype(float)
        g = df.groupby("ticker").agg(disc_ts=("t", "max"), n_trades=("t", "size"), contracts=("c", "sum")).reset_index()
        g.insert(0, "window_t", int(t))
        g.insert(0, "period", per)
        rows.append(g)
        if i % 50 == 0:
            print(per, i, len(g), flush=True)
out = pd.concat(rows)
out.to_csv(OUT, index=False)
print(out.groupby("period").ticker.nunique())
