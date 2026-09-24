"""Stage 1 (Kalshi): enumerate every event of every series (settled or not) -> compact table.

Output: data/round5/m07_prediction_markets/kalshi_events.jsonl.gz (one line per event).
Resumable: series already done are listed in kalshi_events_done.txt.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import get, ROOT  # noqa

B = "https://api.elections.kalshi.com/trade-api/v2"
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
OUT = os.path.join(D, "kalshi_events.jsonl.gz")
DONE = os.path.join(D, "kalshi_events_done.txt")
MAX_PAGES = 100

series = get(B + "/series")["series"]
done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
fo = gzip.open(OUT, "at")
fd = open(DONE, "a")
n = 0
for s in series:
    st = s["ticker"]
    if st in done:
        continue
    cur = None
    for page in range(MAX_PAGES):
        e = get(B + "/events", dict(series_ticker=st, limit=200, cursor=cur), cache=False)
        for ev in e.get("events", []):
            fo.write(json.dumps({
                "series": st, "cat": s.get("category"), "freq": s.get("frequency"),
                "fee_type": s.get("fee_type"), "fee_mult": s.get("fee_multiplier"),
                "event": ev["event_ticker"], "title": ev.get("title"), "sub": ev.get("sub_title"),
                "strike_date": ev.get("strike_date"), "mutex": ev.get("mutually_exclusive"),
            }) + "\n")
        cur = e.get("cursor")
        if not cur or not e.get("events"):
            break
    fo.flush()
    fd.write(st + "\n")
    fd.flush()
    n += 1
    if n % 200 == 0:
        print(n, st, flush=True)
print("done", n)
