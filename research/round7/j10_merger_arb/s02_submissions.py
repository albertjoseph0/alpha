"""EDGAR submissions JSON for every candidate target CIK (filed SC 14D9 / PREM14A / DEFM14A / PREM14C / DEFM14C,
2011Q4..2026Q3). Keeps only filings of interest + company metadata. Fetched uncached (to spare the shared
cache) and saved incrementally as parts: subs/part_XXXX.parquet (filings) and subs/meta_XXXX.parquet.
Older pages ("files") are fetched only when the recent list does not reach back to the first merger filing."""
import json, sys
import pandas as pd
from common import DATA, get

KEEP = {"8-K", "8-K/A", "25", "25-NSE", "15-12B", "15-12G", "15-15D", "15", "DEFM14A", "PREM14A", "DEFM14C",
        "PREM14C", "SC 14D9", "SC 14D9/A", "SC TO-T", "SC TO-T/A", "SC 13E3", "SC14D9C", "10-K", "10-Q",
        "DEFA14A", "DEF 14A", "S-4", "425"}
OUT = DATA / "subs"; OUT.mkdir(exist_ok=True)
d = pd.read_parquet(DATA / "index_rows.parquet")
t = d[d.form.isin(["SC 14D9", "DEFM14A", "PREM14A", "DEFM14C", "PREM14C"])]
first = t.groupby("cik").date.min()
done = set()
for p in OUT.glob("meta_*.parquet"):
    done |= set(pd.read_parquet(p, columns=["cik"]).cik)
todo = [c for c in first.index if c not in done]
print("todo", len(todo), "done", len(done), flush=True)
part = len(list(OUT.glob("meta_*.parquet")))
F, M = [], []
COLS = ["accessionNumber", "filingDate", "reportDate", "form", "items", "primaryDocument", "acceptanceDateTime"]


def frame(block):
    df = pd.DataFrame({c: block.get(c, [None] * len(block["form"])) for c in COLS})
    return df[df.form.isin(KEEP)]


def flush():
    global F, M, part
    if M:
        pd.concat(F).to_parquet(OUT / f"part_{part:04d}.parquet")
        pd.DataFrame(M).to_parquet(OUT / f"meta_{part:04d}.parquet")
        part += 1
    F, M = [], []


for i, cik in enumerate(todo):
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", cache=False))
    except Exception as e:
        M.append(dict(cik=cik, err=str(e)[:200])); continue
    rec = j["filings"]["recent"]
    dfs = [frame(rec)]
    earliest = pd.to_datetime(min(rec["filingDate"])) if rec["filingDate"] else pd.Timestamp("2100-01-01")
    if earliest > first[cik] - pd.Timedelta(days=200):
        for fmeta in j["filings"].get("files", []):
            if pd.to_datetime(fmeta["filingTo"]) < first[cik] - pd.Timedelta(days=400):
                continue
            try:
                jj = json.loads(get("https://data.sec.gov/submissions/" + fmeta["name"], cache=False))
                dfs.append(frame(jj))
            except Exception:
                pass
    f = pd.concat(dfs); f["cik"] = cik
    F.append(f)
    M.append(dict(cik=cik, name=j.get("name"), tickers=",".join(j.get("tickers") or []),
                  exchanges=",".join([x or "" for x in (j.get("exchanges") or [])]), sic=j.get("sic"),
                  sicDescription=j.get("sicDescription"), state=j.get("stateOfIncorporation"),
                  entityType=j.get("entityType"), category=j.get("category"),
                  former=json.dumps(j.get("formerNames") or []), err=None))
    if len(M) >= 100:
        flush(); print(i + 1, flush=True)
flush()
print("done")
