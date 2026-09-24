"""Pull EDGAR full-index form.idx 2009Q3..2026Q3; keep 424B4, S-1, S-1/A, F-1 rows."""
import re, pandas as pd
from common import DATA, get
rows = []
for y in range(2009, 2027):
    for q in (1, 2, 3, 4):
        if (y, q) < (2009, 3) or (y, q) > (2026, 3):
            continue
        txt = get(f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx", cache=(y, q) < (2026, 3))
        for line in txt.splitlines():
            if line.startswith(("424B4 ", "S-1 ", "S-1/A ", "F-1 ", "F-1/A ", "RW ")):
                m = re.match(r"^(\S+(?:/A)?)\s+(.*?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$", line)
                if m:
                    rows.append(m.groups())
        print(y, q, len(rows), flush=True)
df = pd.DataFrame(rows, columns=["form", "company", "cik", "date", "path"])
df.to_csv(DATA / "index_rows.csv", index=False)
print(df.form.value_counts())
