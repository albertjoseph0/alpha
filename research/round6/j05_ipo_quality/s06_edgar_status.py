"""Life-cycle of each IPO issuer from EDGAR submissions JSON: last periodic report, first Form 25 / Form 15
after the IPO, first merger-related filing (DEFM14A, SC 14D9, SC TO-T, PREM14A, SC 13E3, DEFM14C).
Used to (1) classify missing-price names (acquired vs failed vs alive) and (2) date the end of trading.
Output: edgar_status.csv"""
import json
import pandas as pd
from common import DATA, get

m = pd.read_csv(DATA / "meta.csv", parse_dates=["date"])
m = m[m.ipo_text & ~m.blank_check & ~m.units]
op = DATA / "edgar_status.csv"
old = pd.read_csv(op) if op.exists() else pd.DataFrame(columns=["acc"])
have = set(old.acc)
PER = {"10-K", "10-Q", "20-F", "40-F", "10-KT", "10-K405", "6-K"}
MERGE = {"DEFM14A", "DEFM14C", "SC 14D9", "SC TO-T", "PREM14A", "SC 13E3", "PREM14C"}
rows = []
for r in m.itertuples():
    if r.acc in have:
        continue
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(r.cik):010d}.json"))
    except Exception as e:
        rows.append(dict(acc=r.acc, err=str(e)[:100])); continue
    rec = pd.DataFrame(j["filings"]["recent"])[["form", "filingDate"]]
    rec["filingDate"] = pd.to_datetime(rec.filingDate)
    rec = rec[rec.filingDate >= r.date]
    per = rec[rec.form.isin(PER - {"6-K"})].filingDate
    six = rec[rec.form == "6-K"].filingDate
    f25 = rec[rec.form.isin({"25-NSE", "25"})].filingDate
    f15 = rec[rec.form.str.startswith("15-") | (rec.form == "15")].filingDate
    mg = rec[rec.form.isin(MERGE)].filingDate
    rows.append(dict(acc=r.acc, cik=r.cik, sec_tickers=",".join(j.get("tickers") or []),
                     last_periodic=per.max() if len(per) else pd.NaT, last_6k=six.max() if len(six) else pd.NaT,
                     first_25=f25.min() if len(f25) else pd.NaT, first_15=f15.min() if len(f15) else pd.NaT,
                     first_merger=mg.min() if len(mg) else pd.NaT, n_recent=len(j["filings"]["recent"]["form"])))
    if len(rows) % 100 == 0:
        pd.concat([old, pd.DataFrame(rows)]).to_csv(op, index=False); print(len(rows), flush=True)
pd.concat([old, pd.DataFrame(rows)]).to_csv(op, index=False)
print("done", len(rows))
