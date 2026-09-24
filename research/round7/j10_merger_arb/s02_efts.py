"""EDGAR full-text search: 8-K documents containing "Agreement and Plan of Merger" AND "in cash, without interest",
by quarter 2011Q4..2026Q3 (captures cash-merger announcements, Item 1.01, and completions, Items 2.01/3.01/5.01).
Output: efts_8k.parquet (one row per matching document x cik)."""
import json, urllib.parse
import pandas as pd
from common import DATA, get

Q = '"Agreement and Plan of Merger" "in cash, without interest"'
qs = [(2011, 4)] + [(y, q) for y in range(2012, 2027) for q in (1, 2, 3, 4) if (y, q) <= (2026, 3)]
rows = []
for y, q in qs:
    a = f"{y}-{3*q-2:02d}-01"
    b = (pd.Timestamp(a) + pd.offsets.QuarterEnd(0)).strftime("%Y-%m-%d")
    frm = 0
    while True:
        p = dict(q=Q, forms="8-K", dateRange="custom", startdt=a, enddt=b)
        if frm:
            p["from"] = frm
        d = json.loads(get("https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(p), cache=(y, q) < (2026, 3)))
        hits = d["hits"]["hits"]
        for h in hits:
            s = h["_source"]
            adsh, fn = h["_id"].split(":", 1)
            for i, cik in enumerate(s["ciks"]):
                rows.append(dict(cik=int(cik), name=s["display_names"][i] if i < len(s["display_names"]) else "",
                                 adsh=adsh, fn=fn, form=s["form"], ftype=s.get("file_type"), date=s["file_date"],
                                 items=",".join(s.get("items") or []), sic=",".join(s.get("sics") or []),
                                 inc=",".join(s.get("inc_states") or []), biz=",".join(s.get("biz_states") or [])))
        tot = d["hits"]["total"]["value"]
        frm += len(hits)
        if not hits or frm >= tot or frm >= 9900:
            break
    print(y, q, tot, len(rows), flush=True)
df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df.date)
df.to_parquet(DATA / "efts_8k.parquet")
print(len(df), df.adsh.nunique(), df.cik.nunique())
