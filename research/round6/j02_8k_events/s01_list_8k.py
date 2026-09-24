"""List every non-earnings 8-K (form 8-K, no Item 2.02) with at least one relevant item, filed while the
firm was an S&P 500 member (point-in-time intervals from m06, 2019-10..now). Items and acceptance time
come from EDGAR submissions JSON."""
import json
import pandas as pd
from common import DATA, M06, ITEMS, edgar

iv = pd.read_csv(M06 / "sp500_pit_intervals.csv", parse_dates=["start", "end"])
ciks = sorted(set(int(c) for c in iv.cik.dropna()))
rows = []
for i, c in enumerate(ciks):
    d = json.loads(edgar(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
    blocks = [d["filings"]["recent"]]
    for f in d["filings"].get("files", []):
        if f["filingTo"] >= "2019-10-01":
            blocks.append(json.loads(edgar("https://data.sec.gov/submissions/" + f["name"])))
    for b in blocks:
        df = pd.DataFrame({k: b[k] for k in ["accessionNumber", "filingDate", "acceptanceDateTime", "form",
                                              "items", "primaryDocument"]})
        df = df[(df.form == "8-K") & (df.filingDate >= "2019-10-01")]
        df["cik"] = c; df["company"] = d.get("name")
        rows.append(df)
    if i % 100 == 0:
        print(i, len(ciks), flush=True)
ev = pd.concat(rows).drop_duplicates("accessionNumber")
ev["items"] = ev["items"].fillna("")
ev = ev[~ev["items"].str.contains("2.02", regex=False)]
for it in ITEMS:
    ev["i" + it.replace(".", "")] = ev["items"].str.split(",").apply(lambda L: it in L).astype(int)
icols = ["i" + it.replace(".", "") for it in ITEMS]
ev = ev[ev[icols].sum(axis=1) > 0]
ev["accept_et"] = pd.to_datetime(ev.acceptanceDateTime, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
ev["filingDate"] = pd.to_datetime(ev.filingDate)
iv2 = iv.dropna(subset=["cik"]).copy(); iv2["cik"] = iv2.cik.astype(int)
mm = ev.merge(iv2, on="cik")
mm = mm[(mm.filingDate >= mm.start) & (mm.filingDate < mm.end)]
mm = mm.sort_values(["accessionNumber", "ticker"]).drop_duplicates("accessionNumber").drop(columns=["start", "end"])
mm.to_csv(DATA / "events_8k.csv", index=False)
print("events:", len(mm))
print(mm.groupby(mm.filingDate.dt.year).size())
print(mm[icols].sum())
