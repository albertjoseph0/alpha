"""IPO candidate 424B4s: the first 424B4 of a CIK (in the index since 2009Q3) that follows an S-1/F-1
by the same CIK within 3 years. Obvious SPAC names dropped here (Jev/keywords re-check later).
Output: candidates.csv"""
import re, pandas as pd
from common import DATA

df = pd.read_csv(DATA / "index_rows.csv", parse_dates=["date"])
df["cik"] = df.cik.astype(int)
reg = df[df.form.isin(["S-1", "F-1", "S-1/A", "F-1/A"])].groupby("cik").date.min().rename("first_reg")
p = df[df.form == "424B4"].sort_values("date")
first = p.groupby("cik").head(1).merge(reg, left_on="cik", right_index=True, how="left")
c = first[(first.first_reg.notna()) & (first.first_reg <= first.date)
          & ((first.date - first.first_reg).dt.days <= 3 * 365)
          & (first.date >= "2010-01-01")].copy()
spac = re.compile(r"acquisition|merger|blank check|\bSPAC\b|capital corp\b.*\bI+\b", re.I)
c["spac_name"] = c.company.str.contains(spac)
c["reg_form"] = c.cik.map(df[df.form.isin(["S-1", "F-1"])].sort_values("date").groupby("cik").form.first())
c["acc"] = c.path.str.extract(r"/([\d-]+)\.txt$")[0]
print(len(first), len(c), c.spac_name.sum())
print(c[~c.spac_name].groupby(c.date.dt.year).size())
c.to_csv(DATA / "candidates.csv", index=False)
