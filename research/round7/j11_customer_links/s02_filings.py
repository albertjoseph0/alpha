"""All 10-K filings (2011-06..2026-09) of each universe CIK from EDGAR submissions JSON (shared sec.get).
Output: DATA/filings_all.csv (cik, name, sic, form, acc, filing_date, report_date, accept, primary, size)
and DATA/cik_meta.csv (cik, name, sic, former names)."""
import json
import time
from common import *
from secx import fetch, cached

U = pd.read_csv(DATA / "universe.csv")
ciks = sorted(U.cik.dropna().astype(int).unique())
KEEP = {"10-K", "10-K405", "10-KT"}
raw_f, meta_f = DATA / "filings_all.csv", DATA / "cik_meta.csv"
done = set(pd.read_csv(meta_f).cik) if meta_f.exists() else set()
t0 = time.time()
for i, c in enumerate(ciks):
    if c in done:
        continue
    try:
        j = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{c:010d}.json", store=False))
    except Exception as e:
        print("fail", c, e, flush=True)
        continue
    blocks = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        url = "https://data.sec.gov/submissions/" + f["name"]
        # older pages only if already in the shared cache (j01 fetched pages reaching back to 2012-06)
        if f.get("filingTo", "9999") >= "2011-06-01" and (cached(url) or f.get("filingFrom", "0") >= "2011-01-01"):
            try:
                blocks.append(json.loads(fetch(url)))
            except Exception as e:
                print("fail page", c, f["name"], e, flush=True)
    rows = []
    for b in blocks:
        n = len(b["accessionNumber"])
        for k in range(n):
            if b["form"][k] in KEEP and b["filingDate"][k] >= "2011-06-01":
                rows.append((c, b["form"][k], b["accessionNumber"][k], b["filingDate"][k], b["reportDate"][k],
                             b["acceptanceDateTime"][k], b["primaryDocument"][k], b.get("size", [None] * n)[k]))
    if rows:
        pd.DataFrame(rows, columns=["cik", "form", "acc", "filing_date", "report_date", "accept", "primary",
                                    "size"]).to_csv(raw_f, mode="a", header=not raw_f.exists(), index=False)
    former = "|".join(x.get("name", "") for x in j.get("formerNames", []))
    pd.DataFrame([(c, j.get("name"), j.get("sic"), j.get("sicDescription"), former)],
                 columns=["cik", "name", "sic", "sic_desc", "former"]).to_csv(
        meta_f, mode="a", header=not meta_f.exists(), index=False)
    if i % 100 == 0:
        print(i, c, j.get("name"), len(rows), round(time.time() - t0), flush=True)
print("done", round(time.time() - t0))
