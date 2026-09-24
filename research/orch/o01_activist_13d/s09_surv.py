"""Survivorship accounting. Tickers come from EDGAR's CURRENT display names, so a subject that was later acquired,
went bankrupt or deregistered has no ticker (or no yfinance history) and drops out of the priced sample.

  s09_surv.py fetch [n_per_period=400] -> surv_fates.parquet
      Random sample of events whose subject has no usable price series; each subject's EDGAR submission history
      (data.sec.gov/submissions) classifies (i) whether it was a reporting, exchange-listed company at the time
      and (ii) its fate after the 13D: bankrupt (8-K Item 1.03) > acquired (merger proxy / tender / going-private
      filings, or change-in-control 8-K followed by deregistration) > deregistered (Form 15/25, other) > still
      filing > inactive.
"""
import json
import random
import sys

import pandas as pd

from common import D, ROOT

sys.path.insert(0, str(ROOT / "research" / "round5"))
from sec import get  # noqa: E402

PERIODIC = {"10-K", "10-Q", "20-F", "40-F", "10-K405", "10-KSB", "10-QSB", "N-CSR", "N-CSRS", "6-K"}
MERGER = {"DEFM14A", "DEFM14C", "PREM14A", "PREM14C", "SC 14D9", "SC TO-T", "SC 13E3", "SC14D9C"}
DEREG = {"15-12B", "15-12G", "15-15D", "25", "25-NSE", "15F-12B", "15F-12G", "15F-15D"}


def classify(js: dict, fd: pd.Timestamp) -> dict:
    r = js["filings"]["recent"]
    df = pd.DataFrame({"d": pd.to_datetime(r["filingDate"]), "form": r["form"], "items": r.get("items", [""] * len(r["form"]))})
    after = df[df["d"] > fd]
    before = df[(df["d"] <= fd) & (df["d"] >= fd - pd.Timedelta(days=550))]
    reporting = before["form"].isin(PERIODIC).any()
    listed = (df["form"].isin({"15-12B", "25", "25-NSE", "15F-12B"}) & (df["d"] > fd)).any() or \
             (df["form"].isin({"8-A12B"}) & (df["d"] <= fd)).any()
    bank = after[(after["form"] == "8-K") & after["items"].fillna("").str.contains("1.03")]
    merg = after[after["form"].isin(MERGER)]
    dereg = after[after["form"].isin(DEREG)]
    cic = after[(after["form"] == "8-K") & after["items"].fillna("").str.contains("5.01")]
    fate, fdate = "inactive", after["d"].max() if len(after) else pd.NaT
    if len(bank):
        fate, fdate = "bankrupt", bank["d"].min()
    elif len(merg) or (len(cic) and len(dereg)):
        fate = "acquired"
        fdate = dereg["d"].min() if len(dereg) else (merg["d"].max())
    elif len(dereg):
        fate, fdate = "deregistered", dereg["d"].min()
    elif len(after) and after["d"].max() >= pd.Timestamp("2026-01-01"):
        fate, fdate = "still_filing", pd.NaT
    return {"reporting": bool(reporting), "listed": bool(listed), "fate": fate, "fate_date": fdate,
            "days_to_fate": (fdate - fd).days if pd.notna(fdate) else None, "n_filings": len(df),
            "cur_tickers": ",".join(js.get("tickers") or [])}


def fetch(n=400):
    ev = pd.read_parquet(D / "events.parquet")
    miss = ev[ev["entry_date"].isna()].copy()
    miss["period"] = (miss["file_date"] >= "2020-01-01").map({False: "DEV", True: "TEST"})
    rows = []
    for per, g in miss.groupby("period"):
        idx = list(g.index)
        random.Random(0).shuffle(idx)
        for i in idx[:int(n)]:
            r = ev.loc[i]
            try:
                js = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(r['subject_cik']):010d}.json"))
                rows.append({"idx": i, "period": per, "subject_cik": r["subject_cik"], "file_date": r["file_date"],
                             "has_tk": r["has_tk"], **classify(js, r["file_date"])})
            except Exception as e:  # noqa: BLE001
                rows.append({"idx": i, "period": per, "subject_cik": r["subject_cik"], "file_date": r["file_date"],
                             "has_tk": r["has_tk"], "fate": "error", "err": str(e)[:120]})
        print(per, len(rows), flush=True)
    out = pd.DataFrame(rows)
    out.to_parquet(D / "surv_fates.parquet")
    print(pd.crosstab([out["period"], out["reporting"], out["listed"]], out["fate"]))


if __name__ == "__main__":
    fetch(*(sys.argv[2:3] or []))
