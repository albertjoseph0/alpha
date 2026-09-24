"""Stage 3 (Kalshi): market metadata for discovered tickers (batched 50 per call).

usage: k03_meta.py DEV|TEST
Output: data/round5/m07_prediction_markets/kalshi_meta_<PERIOD>.csv.gz
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

B = "https://api.elections.kalshi.com/trade-api/v2"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
disc = pd.read_csv(os.path.join(D, "kalshi_discovery.csv.gz"))
disc = disc[disc.period == per]
tickers = sorted(disc.ticker.unique())
KEEP = ["ticker", "event_ticker", "market_type", "open_time", "close_time", "expected_expiration_time",
        "expiration_time", "latest_expiration_time", "settlement_ts", "can_close_early", "result",
        "settlement_value_dollars", "status", "volume_fp", "title", "yes_sub_title", "no_sub_title",
        "rules_primary", "price_level_structure", "expiration_value"]
rows = []
for i in range(0, len(tickers), 50):
    chunk = tickers[i:i + 50]
    d = get(B + "/historical/markets", dict(tickers=",".join(chunk), limit=1000))
    ms = d.get("markets", [])
    got = {m["ticker"] for m in ms}
    # tickers not archived yet are served by the live endpoint
    miss = [t for t in chunk if t not in got]
    if miss:
        d2 = get(B + "/markets", dict(tickers=",".join(miss), limit=1000))
        ms += d2.get("markets", [])
    for m in ms:
        r = {k: m.get(k) for k in KEEP}
        r["rules_primary"] = (r["rules_primary"] or "")[:300]
        rows.append(r)
    if i % 2000 == 0:
        print(i, len(tickers), len(rows), flush=True)
df = pd.DataFrame(rows).drop_duplicates("ticker")
df.to_csv(os.path.join(D, f"kalshi_meta_{per}.csv.gz"), index=False)
print(per, len(tickers), "->", len(df))
