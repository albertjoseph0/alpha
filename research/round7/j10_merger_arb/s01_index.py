"""EDGAR form.idx 2011Q4..2026Q3 -> rows of merger-related forms (target-side filings + delisting forms).
Output: index_rows.parquet (form, name, cik, date, path)."""
import pandas as pd
from common import DATA, get

FORMS = {"SC TO-T", "SC 14D9", "PREM14A", "DEFM14A", "PREM14C", "DEFM14C", "SC 13E3", "SC14D9C"}
rows = []
qs = [(2011, 4)] + [(y, q) for y in range(2012, 2027) for q in (1, 2, 3, 4) if (y, q) <= (2026, 3)]
for y, q in qs:
    s = get(f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx", cache=(y, q) != (2026, 3))
    for l in s.splitlines():
        f = l[:17].strip()
        if f in FORMS:
            parts = l[17:].rstrip()
            path = parts.split()[-1]; date = parts.split()[-2]; cik = parts.split()[-3]
            name = parts[: parts.rfind(cik)].strip()
            rows.append((f, name, int(cik), date, path))
    print(y, q, len(rows), flush=True)
df = pd.DataFrame(rows, columns=["form", "name", "cik", "date", "path"])
df["date"] = pd.to_datetime(df.date)
df.to_parquet(DATA / "index_rows.parquet")
print(df.form.value_counts())
