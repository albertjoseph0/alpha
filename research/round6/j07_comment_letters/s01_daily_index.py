"""EDGAR daily index (the dissemination feed) 2012Q1..2026Q3 -> every UPLOAD (SEC staff letter) and CORRESP
(company response) row with its public DISSEMINATION date (= the daily-index file date).

Why the daily index: for UPLOAD/CORRESP the EDGAR 'Date Filed' is the letter date, while the public release is
>= 20 business days after the review closes. The daily index lists each filing on the day it was disseminated
(verified: Apple UPLOAD dated 2015-05-19 appears on 2015-10-05; the .hdr.sgml header date agrees).

Output: DATA/daily/YYYYQn.csv (resumable per quarter) and DATA/letters_index.csv (all quarters)."""
import re
import sys
from common import *

OUTD = DATA / "daily"
OUTD.mkdir(exist_ok=True)
ROW = re.compile(r"^(UPLOAD|CORRESP)\s+(.*?)\s+(\d+)\s+(\d{8}|\d{4}-\d{2}-\d{2})\s+(edgar/\S+)\s*$")


def quarters(y0=2012, y1=2026):
    for y in range(y0, y1 + 1):
        for q in range(1, 5):
            if (y, q) > (2026, 3):
                return
            yield y, q


def do_quarter(y, q):
    f = OUTD / f"{y}Q{q}.csv"
    part = OUTD / f"{y}Q{q}.partial.csv"
    if f.exists():
        return
    lst = fetch(f"https://www.sec.gov/Archives/edgar/daily-index/{y}/QTR{q}/").decode("utf-8", "replace")
    names = sorted(set(re.findall(r'href="(form\.(\d{8})\.idx)"', lst)))
    done = set()
    rows = []
    if part.exists():
        P = pd.read_csv(part, dtype=str)
        done = set(P["_day"].unique())
        rows = P.to_dict("records")
    for fn, day in names:
        if day in done:
            continue
        try:
            txt = fetch(f"https://www.sec.gov/Archives/edgar/daily-index/{y}/QTR{q}/{fn}").decode("latin-1")
        except urllib.error.HTTPError as e:
            print("skip", fn, e.code, flush=True)
            continue
        n0 = len(rows)
        for line in txt.splitlines():
            if not (line.startswith("UPLOAD") or line.startswith("CORRESP")):
                continue
            m = ROW.match(line)
            if m:
                rows.append({"form": m[1], "company": m[2].strip(), "cik": m[3], "date_filed": m[4].replace("-", ""),
                             "path": m[5], "dissem": day, "_day": day})
        if len(rows) == n0:  # keep a marker so that the day counts as done
            rows.append({"form": "NONE", "company": "", "cik": "0", "date_filed": day, "path": "", "dissem": day, "_day": day})
        pd.DataFrame(rows).to_csv(part, index=False)
    D = pd.DataFrame(rows)
    D.to_csv(f, index=False)
    part.unlink(missing_ok=True)
    print(y, q, len(names), "days", (D.form == "UPLOAD").sum(), "UPLOAD", (D.form == "CORRESP").sum(), "CORRESP", flush=True)


if __name__ == "__main__":
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2012
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    for y, q in quarters(y0, y1):
        do_quarter(y, q)
    fs = sorted(OUTD.glob("20??Q?.csv"))
    A = pd.concat([pd.read_csv(x, dtype=str) for x in fs])
    A = A[A.form != "NONE"].drop(columns="_day")
    A["acc"] = A.path.str.extract(r"/([\d-]+)\.txt$")[0]
    A.to_csv(DATA / "letters_index.csv", index=False)
    print("total", len(A), A.form.value_counts().to_dict())
