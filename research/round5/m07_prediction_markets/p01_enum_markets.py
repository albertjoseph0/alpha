"""Stage 1 (Polymarket): enumerate closed markets from gamma-api by endDate windows (10-day chunks).

Output: data/round5/m07_prediction_markets/poly_markets.csv.gz (compact metadata only).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

G = "https://gamma-api.polymarket.com/markets"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
OUT = os.path.join(D, "poly_markets.csv.gz")

KEEP = ["id", "question", "conditionId", "slug", "endDate", "startDate", "createdAt", "closedTime",
        "outcomes", "outcomePrices", "volumeNum", "volumeClob", "clobTokenIds", "negRisk",
        "umaResolutionStatus", "enableOrderBook", "feesEnabled", "feeType", "takerBaseFee",
        "hasReviewedDates", "category", "groupItemTitle", "automaticallyResolved", "resolvedBy",
        "archived", "restricted", "orderPriceMinTickSize", "lastTradePrice", "bestAsk", "bestBid"]

rows = []
t = datetime(2020, 9, 1, tzinfo=timezone.utc)
end = datetime(2026, 9, 20, tzinfo=timezone.utc)
step = timedelta(days=10)
while t < end:
    a, b = t, t + step
    off = 0
    while True:
        d = get(G, dict(closed="true", limit=500, offset=off,
                        end_date_min=a.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        end_date_max=b.strftime("%Y-%m-%dT%H:%M:%SZ")), cache=False)
        if not isinstance(d, list) or not d:
            break
        for m in d:
            r = {k: m.get(k) for k in KEEP}
            ev = (m.get("events") or [{}])[0]
            r["event_id"] = ev.get("id")
            r["event_slug"] = ev.get("slug")
            r["event_title"] = ev.get("title")
            r["event_endDate"] = ev.get("endDate")
            r["tags"] = None
            rows.append(r)
        off += len(d)
    print(a.date(), len(rows), flush=True)
    t = b
df = pd.DataFrame(rows).drop_duplicates("id")
df.to_csv(OUT, index=False)
print(len(df))
