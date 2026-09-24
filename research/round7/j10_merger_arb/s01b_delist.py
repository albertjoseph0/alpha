"""form.idx (cached) -> delisting / deregistration rows (25, 25-NSE, 15-*) and tender amendments.
Output: delist_rows.parquet (form, name, cik, date, path)."""
import pandas as pd
from common import DATA, get

FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15-15D", "15F-12B", "15F-12G", "15F-15D", "SC TO-T/A", "SC 14D9/A"}
rows = []
qs = [(2011, 4)] + [(y, q) for y in range(2012, 2027) for q in (1, 2, 3, 4) if (y, q) <= (2026, 3)]
for y, q in qs:
    s = get(f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx")
    for l in s.splitlines():
        f = l[:17].strip()
        if f in FORMS:
            parts = l[17:].rstrip().split()
            rows.append((f, " ".join(parts[:-3]), int(parts[-3]), parts[-2], parts[-1]))
df = pd.DataFrame(rows, columns=["form", "name", "cik", "date", "path"])
df["date"] = pd.to_datetime(df.date)
df.to_parquet(DATA / "delist_rows.parquet")
print(df.form.value_counts())
