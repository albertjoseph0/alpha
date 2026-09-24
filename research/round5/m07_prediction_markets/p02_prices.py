"""Stage 2 (Polymarket): hourly price history (clob prices-history, first outcome token) for the 8 days
before each market's scheduled endDate (the ex-ante anchor), for binary CLOB markets.

usage: p02_prices.py DEV|TEST [max_markets]
Input : poly_markets_<range>.csv.gz from p01
Output: poly_sample_<PER>.csv.gz (market list) and poly_hist_<PER>.pkl.gz dict id -> np.ndarray [n, 2] (t, p_outcome0)
Selection uses no outcome information (binary, order book enabled, endDate/closedTime in period).
"""
import gzip
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
SPLIT = pd.Timestamp("2024-07-01", tz="UTC")
src = {"DEV": "poly_markets_20200901_20240701.csv.gz", "TEST": "poly_markets_20240701_20260901.csv.gz"}[per]
df = pd.read_csv(os.path.join(D, src), low_memory=False)
df["end_dt"] = pd.to_datetime(df.endDate, utc=True, errors="coerce", format="ISO8601")
df["closed_dt"] = pd.to_datetime(df.closedTime, utc=True, errors="coerce", format="ISO8601")
df = df[df.clobTokenIds.notna() & df.end_dt.notna() & df.closed_dt.notna()]
df = df[df.outcomes.map(lambda s: len(json.loads(s)) == 2 if isinstance(s, str) else False)]
df = df[(df.closed_dt < SPLIT)] if per == "DEV" else df[(df.closed_dt >= SPLIT)]
# CLOB launched late 2022; earlier (AMM) markets have no price history
df = df[df.end_dt >= pd.Timestamp("2022-10-01", tz="UTC")]
df["anchor_ts"] = df.end_dt.pipe(lambda x: (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()).astype("int64")
df["closed_ts"] = df.closed_dt.pipe(lambda x: (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()).astype("int64")
df["tok0"] = df.clobTokenIds.map(lambda s: json.loads(s)[0])
df = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
df.drop(columns=["clobTokenIds"]).to_csv(os.path.join(D, f"poly_sample_{per}.csv.gz"), index=False)
print(per, "markets", len(df), flush=True)

OUT = os.path.join(D, f"poly_hist_{per}.pkl.gz")
res = {}
if os.path.exists(OUT):
    with gzip.open(OUT, "rb") as f:
        res = pickle.load(f)
for i, r in enumerate(df.head(cap).itertuples()):
    if r.id in res:
        continue
    end = int(min(r.anchor_ts, r.closed_ts)) + 3600
    start = int(r.anchor_ts - 8 * 86400)
    if end <= start:
        res[r.id] = np.zeros((0, 2))
        continue
    h = get("https://clob.polymarket.com/prices-history", dict(market=r.tok0, startTs=start, endTs=end, fidelity=60))
    hh = h.get("history", []) if isinstance(h, dict) else []
    res[r.id] = np.array([[x["t"], x["p"]] for x in hh], dtype=float) if hh else np.zeros((0, 2))
    if i % 250 == 0:
        print(i, len(df), flush=True)
        with gzip.open(OUT, "wb") as fo:
            pickle.dump(res, fo)
with gzip.open(OUT, "wb") as fo:
    pickle.dump(res, fo)
print("done", len(res))
