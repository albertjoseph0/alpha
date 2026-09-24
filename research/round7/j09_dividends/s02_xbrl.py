"""XBRL dividends-per-share facts for universe CIKs, read from the shared bulk companyfacts.zip without extracting it.
Concepts: us-gaap CommonStockDividendsPerShareDeclared (primary), CommonStockDividendsPerShareCashPaid (fallback).
-> DATA/dps_facts.parquet [cik, concept, start, end, val, accn, fy, fp, form, filed, frame]"""
import json, zipfile
import pandas as pd
from common import DATA, ROOT

CONCEPTS = ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]
u = pd.read_parquet(DATA / "universe_monthly.parquet", columns=["cik"])
ciks = sorted(set(int(c) for c in u.cik.dropna()))
z = zipfile.ZipFile(ROOT / "data/shared/companyfacts.zip")
names = set(z.namelist())
rows, miss = [], 0
for i, c in enumerate(ciks):
    fn = f"CIK{c:010d}.json"
    if fn not in names:
        miss += 1
        continue
    j = json.loads(z.read(fn))
    g = j.get("facts", {}).get("us-gaap", {})
    for con in CONCEPTS:
        for unit, facts in g.get(con, {}).get("units", {}).items():
            for f in facts:
                rows.append({"cik": c, "concept": con, "unit": unit, "start": f.get("start"), "end": f.get("end"),
                             "val": f.get("val"), "accn": f.get("accn"), "fy": f.get("fy"), "fp": f.get("fp"),
                             "form": f.get("form"), "filed": f.get("filed"), "frame": f.get("frame")})
    if i % 200 == 0:
        print(i, len(rows), flush=True)
d = pd.DataFrame(rows)
for k in ("start", "end", "filed"):
    d[k] = pd.to_datetime(d[k])
d.to_parquet(DATA / "dps_facts.parquet")
print("ciks", len(ciks), "missing json", miss, "facts", len(d), "ciks with facts", d.cik.nunique())
print(d.groupby("concept").cik.nunique())
