"""Stage 2 (Polymarket TEST): seeded, outcome-blind subsample + hourly prices, memory-safe (chunked read).

usage: p03_test_sample.py [N=5000]
The TEST enumeration has 2.63M markets (mostly 5/15-min crypto and sports props), so p02's full-file load
is not feasible.  Universe (all ex-ante, no outcome information):
  binary CLOB markets, closedTime in [2024-07-01, 2026-09-01), endDate >= 2022-10-01, and listed long enough
  for the frozen H=72h rule: startDate <= endDate - 73h (the market exists at the signal bar d-1h).
Sample: N markets drawn with random_state=20260924 (pre-registered in PREREG.md), then fetched in that order.
Output: poly_sample_TEST.csv.gz, poly_hist_TEST.pkl.gz (same format as p02)
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
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
SPLIT, END = pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC")
COLS = ["id", "question", "endDate", "startDate", "createdAt", "closedTime", "outcomes", "outcomePrices", "volumeNum",
        "clobTokenIds", "negRisk", "umaResolutionStatus", "enableOrderBook", "feesEnabled", "feeType", "takerBaseFee",
        "category", "event_id", "event_slug", "series_slug"]
SAMP = os.path.join(D, "poly_sample_TEST.csv.gz")


def ts(x):
    return (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()


if not os.path.exists(SAMP):
    keep = []
    for ch in pd.read_csv(os.path.join(D, "poly_markets_20240701_20260901.csv.gz"), usecols=COLS, chunksize=200_000,
                          low_memory=False, dtype={"id": str, "event_id": str}):
        ch = ch[ch.clobTokenIds.notna() & ch.outcomes.notna()]
        ch["end_dt"] = pd.to_datetime(ch.endDate, utc=True, errors="coerce", format="ISO8601")
        ch["closed_dt"] = pd.to_datetime(ch.closedTime, utc=True, errors="coerce", format="ISO8601")
        st = pd.to_datetime(ch.startDate, utc=True, errors="coerce", format="ISO8601")
        cr = pd.to_datetime(ch.createdAt, utc=True, errors="coerce", format="ISO8601")
        ch["list_dt"] = st.fillna(cr)
        ch = ch[ch.end_dt.notna() & ch.closed_dt.notna() & ch.list_dt.notna()]
        ch = ch[(ch.closed_dt >= SPLIT) & (ch.closed_dt < END) & (ch.end_dt >= pd.Timestamp("2022-10-01", tz="UTC"))]
        ch = ch[ch.list_dt <= ch.end_dt - pd.Timedelta(hours=73)]
        ch = ch[ch.outcomes.map(lambda s: len(json.loads(s)) == 2)]
        keep.append(ch.drop(columns=["list_dt"]))
        print("chunk", sum(len(k) for k in keep), flush=True)
    df = pd.concat(keep).drop_duplicates("id")
    print("TEST universe (H=72-eligible binary CLOB markets):", len(df), "events", df.event_id.nunique(), flush=True)
    df = df.sample(n=min(N, len(df)), random_state=20260924).reset_index(drop=True)
    df["anchor_ts"] = ts(df.end_dt).astype("int64")
    df["closed_ts"] = ts(df.closed_dt).astype("int64")
    df["tok0"] = df.clobTokenIds.map(lambda s: json.loads(s)[0])
    df.drop(columns=["clobTokenIds", "end_dt", "closed_dt"]).to_csv(SAMP, index=False)
df = pd.read_csv(SAMP, low_memory=False, dtype={"id": str, "event_id": str, "tok0": str})
print("TEST sample", len(df), flush=True)

OUT = os.path.join(D, "poly_hist_TEST.pkl.gz")
res = {}
if os.path.exists(OUT):
    with gzip.open(OUT, "rb") as f:
        res = pickle.load(f)
for i, r in enumerate(df.itertuples()):
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
