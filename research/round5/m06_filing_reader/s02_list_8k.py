"""List all 8-K (and 8-K/A excluded) filings with Item 2.02 for universe CIKs, 2019-10 .. now,
from EDGAR submissions JSON (gives items + acceptanceDateTime). Keep only filings made while the
firm was an S&P 500 member (point-in-time)."""
import json
import pandas as pd
from common import DATA, fetch

iv = pd.read_csv(DATA / "sp500_pit_intervals.csv", parse_dates=["start", "end"])
ciks = sorted(set(int(c) for c in iv.cik.dropna()))
rows = []
for i, c in enumerate(ciks):
    js = fetch(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
    if js is None:
        print("missing", c); continue
    d = json.loads(js)
    blocks = [d["filings"]["recent"]]
    for f in d["filings"].get("files", []):
        if f["filingTo"] >= "2019-10-01":
            j2 = fetch("https://data.sec.gov/submissions/" + f["name"])
            if j2: blocks.append(json.loads(j2))
    for b in blocks:
        df = pd.DataFrame({k: b[k] for k in ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "items", "primaryDocument"]})
        df = df[(df.form == "8-K") & df["items"].str.contains("2.02", regex=False) & (df.filingDate >= "2019-10-01")]
        df["cik"] = c; df["company"] = d.get("name")
        rows.append(df)
    if i % 50 == 0:
        print(i, len(ciks), sum(len(r) for r in rows), flush=True)
ev = pd.concat(rows).drop_duplicates("accessionNumber")
# acceptanceDateTime is true UTC (verified: AAPL 2026-07-30T20:30:28Z == header ACCEPTANCE-DATETIME 16:30:28 ET)
ev["accept_et"] = pd.to_datetime(ev.acceptanceDateTime, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
ev["filingDate"] = pd.to_datetime(ev.filingDate)
# point-in-time membership: filing date inside [start, end) of some interval for that CIK
iv2 = iv.dropna(subset=["cik"]).copy(); iv2["cik"] = iv2.cik.astype(int)
mm = ev.merge(iv2, on="cik")
mm = mm[(mm.filingDate >= mm.start) & (mm.filingDate < mm.end)]
# one ticker per accession (dual share classes): alphabetical first
mm = mm.sort_values(["accessionNumber", "ticker"]).drop_duplicates("accessionNumber")
mm = mm.drop(columns=["start", "end"])
mm.to_csv(DATA / "events_8k202.csv", index=False)
print("8-K 2.02 in window:", len(ev), " while S&P500 member:", len(mm))
print(mm.groupby(mm.filingDate.dt.year).size())
