"""Quarterly EDGAR form.idx 2011Q3..2026Q3 (cached by the shared sec.get) -> UPLOAD and CORRESP rows for the
804 CIKs that were ever S&P 500 members 2011-12..2026-09. 'Date Filed' here is the LETTER date; the public
dissemination date comes from each letter's own header (s02) and was validated against the daily index (s01,
2012Q1 sample; the full daily-index crawl was dropped because the shared SEC rate limit gave ~0.4 req/s).
Output: DATA/qindex.csv (form, company, cik, date_filed, path, acc)."""
import re
from common import *

U = pd.read_csv(DATA / "universe_monthly.csv")
ciks = set(U.cik.astype(int))
ROW = re.compile(r"^(UPLOAD|CORRESP)\s+(.*?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2}|\d{8})\s+(edgar/\S+)\s*$")
rows = []
for y in range(2011, 2027):
    for q in range(1, 5):
        if (y, q) < (2011, 3) or (y, q) > (2026, 3):
            continue
        s = sec.get(f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx", cache=(y, q) != (2026, 3))
        n = 0
        for line in s.splitlines():
            if line.startswith("UPLOAD") or line.startswith("CORRESP"):
                m = ROW.match(line)
                if m and int(m[3]) in ciks:
                    rows.append((m[1], m[2].strip(), int(m[3]), m[4].replace("-", ""), m[5]))
                    n += 1
        print(y, q, n, flush=True)
Q = pd.DataFrame(rows, columns=["form", "company", "cik", "date_filed", "path"])
Q["acc"] = Q.path.str.extract(r"/([\d-]+)\.txt$")[0]
Q.to_csv(DATA / "qindex.csv", index=False)
print(Q.form.value_counts().to_dict(), "unique UPLOAD acc:", Q[Q.form == "UPLOAD"].acc.nunique())
