"""Stage 5 (Kalshi): build the market sample for candle download.

usage: k05_build.py DEV|TEST
Inputs : kalshi_meta_<PER>.csv.gz, kalshi_discovery.csv.gz, cached /series (category, fee multiplier)
Output : kalshi_sample_<PER>.csv.gz  (ticker, series, event, category, fee_mult, open_ts, anchor_ts=close_ts,
         settle_ts, can_close_early, result, disc_first_ts, archived)

Selection uses NO outcome information: binary markets whose settlement falls in the period and that were
seen on the trade tape (at a random sampling time) before their close.  The per-horizon ex-ante
discovery filter (disc_ts <= decision time) is applied later in the analysis.
"""
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

B = "https://api.elections.kalshi.com/trade-api/v2"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
SPLIT = pd.Timestamp("2024-07-01", tz="UTC")

meta = pd.read_csv(os.path.join(D, f"kalshi_meta_{per}.csv.gz"))
disc = pd.read_csv(os.path.join(D, "kalshi_discovery.csv.gz"))
disc = disc[disc.period == per]
# every (window, ticker) sighting is kept for the analysis; here we only need the first sighting
first = disc.groupby("ticker").disc_ts.min().rename("disc_first_ts")

ser = pd.DataFrame(get(B + "/series")["series"])[["ticker", "category", "fee_type", "fee_multiplier", "frequency"]]
ser = ser.rename(columns={"ticker": "series"})


def tsz(s):
    return pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601")


m = meta.copy()
m["series"] = m.event_ticker.str.split("-").str[0]
m = m.merge(ser, on="series", how="left")
m["open_ts"] = tsz(m.open_time).pipe(lambda x: (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()).astype("int64")
m["close_dt"] = tsz(m.close_time)
m["settle_dt"] = tsz(m.settlement_ts).fillna(tsz(m.close_time))
m["anchor_ts"] = m.close_dt.pipe(lambda x: (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()).astype("int64")
m["settle_ts"] = m.settle_dt.pipe(lambda x: (x - pd.Timestamp(0, tz="UTC")).dt.total_seconds()).astype("int64")
m = m.merge(first, left_on="ticker", right_index=True, how="left")
n0 = len(m)
m = m[m.market_type == "binary"]
end = m.settle_dt.fillna(m.close_dt)
m = m[(end < SPLIT)] if per == "DEV" else m[(end >= SPLIT)]
m = m[m.disc_first_ts < m.anchor_ts]
m["archived"] = True
cols = ["ticker", "series", "event_ticker", "category", "fee_type", "fee_multiplier", "frequency", "open_ts",
        "anchor_ts", "settle_ts", "can_close_early", "result", "status", "volume_fp", "disc_first_ts", "archived",
        "title", "yes_sub_title", "close_time", "expected_expiration_time", "latest_expiration_time"]
m = m[cols].sample(frac=1.0, random_state=7).reset_index(drop=True)
if per == "TEST":
    # TEST is ~3x larger; keep a seeded random 35% of EVENTS (all their markets), chosen blind to outcomes
    ev = pd.Series(sorted(m.event_ticker.unique()))
    keep = set(ev.sample(frac=0.35, random_state=20260924))
    m = m[m.event_ticker.isin(keep)].reset_index(drop=True)
m.to_csv(os.path.join(D, f"kalshi_sample_{per}.csv.gz"), index=False)
print(per, "meta", n0, "-> sample", len(m), "events", m.event_ticker.nunique(), "series", m.series.nunique())
print(m.category.value_counts().head(12))
print("can_close_early", m.can_close_early.value_counts().to_dict())  # (no outcome columns printed)
