"""Stage 1 (Polymarket): enumerate closed markets from gamma-api by endDate windows (5-day chunks).

v2 (round 5b): uses /markets/keyset (cursor pagination) because /markets refuses offset > ~2000.
Resumable: each window is written to poly_parts/<start>.csv.gz; finished windows are skipped.
usage: p01_enum_markets.py [start YYYY-MM-DD] [end YYYY-MM-DD]
Output (after concatenation): data/round5/m07_prediction_markets/poly_markets_<start>_<end>.csv.gz
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

G = "https://gamma-api.polymarket.com/markets/keyset"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
PARTS = os.path.join(D, "poly_parts")
os.makedirs(PARTS, exist_ok=True)

KEEP = ["id", "question", "conditionId", "slug", "endDate", "startDate", "createdAt", "closedTime",
        "outcomes", "outcomePrices", "volumeNum", "volumeClob", "clobTokenIds", "negRisk",
        "umaResolutionStatus", "enableOrderBook", "feesEnabled", "feeType", "takerBaseFee",
        "hasReviewedDates", "category", "groupItemTitle", "automaticallyResolved", "resolvedBy",
        "archived", "restricted", "orderPriceMinTickSize", "lastTradePrice", "bestAsk", "bestBid",
        "umaEndDate", "updatedAt"]

a0 = datetime.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2020-09-01").replace(tzinfo=timezone.utc)
e0 = datetime.fromisoformat(sys.argv[2] if len(sys.argv) > 2 else "2024-07-01").replace(tzinfo=timezone.utc)
step = timedelta(days=5)
t = a0
while t < e0:
    a, b = t, min(t + step, e0)
    part = os.path.join(PARTS, a.strftime("%Y%m%d") + "_" + b.strftime("%Y%m%d") + ".csv.gz")
    t = b
    if os.path.exists(part):
        continue
    def fetch(a, b):
        rows, cur = [], None
        for _ in range(2000):
            d = get(G, dict(closed="true", limit=500, after_cursor=cur,
                            end_date_min=a.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            end_date_max=b.strftime("%Y-%m-%dT%H:%M:%SZ")), cache=False, tries=4)
            ms = d.get("markets", []) if isinstance(d, dict) else []
            for m in ms:
                r = {k: m.get(k) for k in KEEP}
                ev = (m.get("events") or [{}])[0]
                r["event_id"] = ev.get("id")
                r["event_slug"] = ev.get("slug")
                r["event_title"] = ev.get("title")
                r["event_endDate"] = ev.get("endDate")
                r["series_slug"] = ev.get("seriesSlug")
                rows.append(r)
            cur = d.get("next_cursor") if isinstance(d, dict) else None
            if not cur or not ms:
                break
        return rows

    try:
        rows = fetch(a, b)
    except RuntimeError:
        # some cursors are refused (403 from the CDN); retry the window as 6-hour sub-windows
        rows = []
        u = a
        while u < b:
            v = min(u + timedelta(hours=6), b)
            try:
                rows += fetch(u, v)
            except RuntimeError:
                print("PARTIAL window", u, v, flush=True)
            u = v
    pd.DataFrame(rows, columns=KEEP + ["event_id", "event_slug", "event_title", "event_endDate", "series_slug"]) \
        .to_csv(part, index=False)
    print(a.date(), len(rows), flush=True)
fs = sorted(f for f in os.listdir(PARTS) if a0.strftime("%Y%m%d") <= f[:8] < e0.strftime("%Y%m%d"))
df = pd.concat([pd.read_csv(os.path.join(PARTS, f)) for f in fs]).drop_duplicates("id")
df.to_csv(os.path.join(D, f"poly_markets_{a0:%Y%m%d}_{e0:%Y%m%d}.csv.gz"), index=False)
print("total", len(df))
