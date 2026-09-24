"""List initial Schedule 13D filings (SC 13D until Dec 2024, SCHEDULE 13D after) via EDGAR full-text search.

Writes data/orch/o01_activist_13d/filings.csv: one row per accession with the subject company (the first
CIK in the hit, which EDGAR lists as the subject) and its current ticker if EDGAR shows one.
"""
import json
import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
from sec import get  # noqa: E402

OUT = ROOT / "data" / "orch" / "o01_activist_13d"
OUT.mkdir(parents=True, exist_ok=True)
TICK = re.compile(r"\(([A-Z0-9.\-]{1,6})(?:,\s*[A-Z0-9.\-]{1,6})*\)\s+\(CIK")


def month_hits(form: str, start: str, end: str):
    rows, frm = [], 0
    while True:
        u = (f"https://efts.sec.gov/LATEST/search-index?forms={form.replace(' ', '%20')}"
             f"&dateRange=custom&startdt={start}&enddt={end}&from={frm}")
        d = json.loads(get(u))
        hits = d["hits"]["hits"]
        for h in hits:
            s = h["_source"]
            rows.append({"adsh": s["adsh"], "doc": h["_id"].split(":", 1)[1], "file_date": s["file_date"],
                         "form": s["form"], "ciks": "|".join(s.get("ciks", [])),
                         "names": "|".join(s.get("display_names", [])), "sics": "|".join(s.get("sics", []) or [])})
        frm += len(hits)
        if not hits or frm >= d["hits"]["total"]["value"] or frm >= 10000:
            return rows


def main():
    rows = []
    for m in pd.period_range("2013-01", "2026-08", freq="M"):
        start, end = str(m.start_time.date()), str(m.end_time.date())
        for form in ("SC 13D", "SCHEDULE 13D"):
            if form == "SCHEDULE 13D" and m < pd.Period("2024-12", "M"):
                continue
            rows += month_hits(form, start, end)
        print(m, len(rows), flush=True)
    df = pd.DataFrame(rows)
    df = df[df["form"].isin(["SC 13D", "SCHEDULE 13D"])]
    # one row per accession: prefer the main document (not an exhibit)
    df["is_ex"] = df["doc"].str.lower().str.contains(r"ex|exhibit", regex=True)
    df = df.sort_values(["adsh", "is_ex"]).drop_duplicates("adsh")
    first = df["names"].str.split("|").str[0]
    df["subject_cik"] = df["ciks"].str.split("|").str[0]
    df["subject_name"] = first.str.replace(r"\s+\(CIK.*", "", regex=True)
    df["ticker"] = first.str.extract(TICK, expand=False)
    df["filer_names"] = df["names"].str.split("|").str[1:].str.join(" | ")
    df.drop(columns=["is_ex"]).to_csv(OUT / "filings.csv", index=False)
    print("filings", len(df), "with ticker", df["ticker"].notna().sum())


if __name__ == "__main__":
    main()
