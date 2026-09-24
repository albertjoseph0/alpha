"""Extract point-in-time fundamentals for universe CIKs from the shared bulk companyfacts.zip (read-only):
dei:EntityPublicFloat (USD, as of Q2 end, from 10-K covers), us-gaap StockholdersEquity (fallback: incl. NCI).
Every value keeps its `filed` date, so features use only values filed before the announcement.
Output DATA/facts.parquet: cik, concept, end, filed, val."""
import json, zipfile
from common import *

U = pd.read_parquet(DATA / "universe.parquet")
ciks = sorted(set(U.cik.dropna().astype(int)))
z = zipfile.ZipFile(ROOT / "data/shared/companyfacts.zip")
names = set(z.namelist())
CON = [("dei", "EntityPublicFloat"), ("us-gaap", "StockholdersEquity"),
       ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")]
rows, miss = [], 0
for i, c in enumerate(ciks):
    fn = f"CIK{c:010d}.json"
    if fn not in names:
        miss += 1; continue
    d = json.loads(z.read(fn))["facts"]
    for ns, con in CON:
        for v in d.get(ns, {}).get(con, {}).get("units", {}).get("USD", []):
            if v.get("filed") and v.get("end") and v["filed"] >= "2010-01-01":
                rows.append((c, con, v["end"], v["filed"], float(v["val"])))
    if i % 200 == 0:
        print(i, len(rows), flush=True)
F = pd.DataFrame(rows, columns=["cik", "concept", "end", "filed", "val"]).drop_duplicates()
F["end"] = pd.to_datetime(F.end); F["filed"] = pd.to_datetime(F.filed)
F.to_parquet(DATA / "facts.parquet", index=False)
print("rows", len(F), "ciks", F.cik.nunique(), "missing files", miss)
print(F.groupby("concept").cik.nunique())
