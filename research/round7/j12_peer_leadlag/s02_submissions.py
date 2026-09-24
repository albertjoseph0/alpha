"""EDGAR submissions JSON per universe CIK (via the shared sec.get; j01 already cached most S&P 500 CIKs).
Outputs: DATA/subm_rows.csv (10-K filings 2010-06+, resumable), DATA/firms.csv (cik, name, sic, former names)."""
import json
import time
from common import *
from sec import get

U = pd.read_parquet(DATA / "universe_monthly.parquet")
TEXT_YEARS = [2012, 2015, 2018, 2021, 2024]          # 3-year text formations (end of April)
u = U[(U.month_end.dt.month == FORM_MONTH) & U.month_end.dt.year.isin(TEXT_YEARS) & U.has_px].dropna(subset=["cik"])
need_from = (u.groupby(u.cik.astype(int)).month_end.min().dt.year - 1).astype(str) + "-01-01"  # 10-Ks from Jan of prior yr
ciks = sorted(need_from.index)
print("CIKs needed:", len(ciks), flush=True)
KEEP = {"10-K", "10-K405", "10-KT"}
raw_f = DATA / "subm_rows.csv"
firm_f = DATA / "firms.jsonl"
done = set()
if firm_f.exists():
    done = {json.loads(l)["cik"] for l in open(firm_f)}
t0 = time.time()
for i, c in enumerate(ciks):
    if c in done:
        continue
    if time.time() - t0 > 18 * 60:
        print("time box reached", flush=True)
        raise SystemExit(0)
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
    except Exception as e:
        print("fail", c, e, flush=True)
        continue
    blocks = [j["filings"]["recent"]]
    oldest = min(blocks[0]["filingDate"]) if blocks[0]["filingDate"] else "0"
    nf = need_from[c]
    if oldest > nf:
        for f in j["filings"].get("files", []):
            if f.get("filingTo", "9999") >= nf:
                try:
                    blocks.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
                except Exception as e:
                    print("fail page", c, f["name"], e, flush=True)
    rows = []
    for b in blocks:
        n = len(b["accessionNumber"])
        for k in range(n):
            if b["form"][k] in KEEP and b["filingDate"][k] >= "2010-06-01":
                rows.append((c, b["form"][k], b["accessionNumber"][k], b["filingDate"][k], b["reportDate"][k],
                             b["acceptanceDateTime"][k], b["primaryDocument"][k]))
    if rows:
        pd.DataFrame(rows, columns=["cik", "form", "acc", "filing_date", "report_date", "accept", "primary"]).to_csv(
            raw_f, mode="a", header=not raw_f.exists(), index=False)
    rec = {"cik": int(c), "name": j.get("name"), "sic": j.get("sic"), "sic_desc": j.get("sicDescription"),
           "tickers": j.get("tickers"), "former": j.get("formerNames", [])}
    with open(firm_f, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    if i % 100 == 0:
        print(i, c, j.get("name"), len(rows), round(time.time() - t0), flush=True)
print("done", len(ciks), round(time.time() - t0))
(DATA / "s02_done").write_text("ok")
