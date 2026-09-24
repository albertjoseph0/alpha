"""Build deal episodes from EFTS 8-K hits (cash-merger 1.01 announcements), form.idx entry documents
(SC TO-T offer / DEFM14A / DEFM14C filed for the target) and delisting forms (25/25-NSE/15-*).

Episode = first cash-merger 1.01 8-K of a target CIK that is followed within 240 days by an entry document.
Entry doc = the earliest original SC TO-T (tender) or DEFM14A/DEFM14C (vote/consent) for the target after the
announcement. Delisting = first 25/25-NSE/15-* for the CIK after the entry doc (outcome, used only as a label).
Output: deals.parquet (one row per episode) + docs list for fetching."""
import pandas as pd
from common import DATA

ix = pd.read_parquet(DATA / "index_rows.parquet")
dl = pd.read_parquet(DATA / "delist_rows.parquet")
ef = pd.read_parquet(DATA / "efts_8k.parquet")

T = set(ix[ix.form.isin(["SC 14D9", "DEFM14A", "PREM14A", "DEFM14C", "PREM14C"])].cik)
ef = ef[ef.form == "8-K"]
ann = ef[ef["items"].str.contains(r"1\.01") & ef.cik.isin(T)]
BODY_PRI = {"8-K": 0, "EX-99.1": 1, "EX-99": 2}


def pick_doc(g):
    g = g.assign(pr=g.ftype.map(BODY_PRI).fillna(5)).sort_values(["pr", "fn"])
    return g.iloc[0]


a = (ann.groupby(["cik", "adsh"], group_keys=False).apply(pick_doc).reset_index(drop=True)
     .sort_values(["cik", "date"]))
comp = ef[ef["items"].str.contains(r"2\.01|3\.01|5\.01") & ef.cik.isin(T)]
comp = comp.groupby(["cik", "adsh"], group_keys=False).apply(pick_doc).reset_index(drop=True)

ent = ix[ix.form.isin(["SC TO-T", "DEFM14A", "DEFM14C"])].copy()
# a SC TO-T row is listed under both bidder and subject: keep it only if the CIK filed a SC 14D9 within 10 days
d9 = ix[ix.form == "SC 14D9"][["cik", "date"]].rename(columns={"date": "d9"})
tot = ent[ent.form == "SC TO-T"].reset_index().merge(d9, on="cik")
tot = tot[(tot.d9 - tot.date).dt.days.abs() <= 10]["index"].unique()
ent = ent[(ent.form != "SC TO-T") | ent.index.isin(tot)]
ent = ent.sort_values(["cik", "date"])
dls = dl[dl.form.isin(["25", "25-NSE", "15-12B", "15-12G", "15-15D"])].sort_values(["cik", "date"])

rows = []
for cik, ga in a.groupby("cik"):
    ge = ent[ent.cik == cik]
    gd = dls[dls.cik == cik]
    busy_until = pd.Timestamp("1900-01-01")
    for r in ga.itertuples():
        if r.date <= busy_until:
            continue
        e = ge[(ge.date >= r.date) & (ge.date <= r.date + pd.Timedelta(days=240))]
        if e.empty:
            continue
        e0 = e.iloc[0]
        d = gd[gd.date > e0.date]
        d0 = d.iloc[0] if len(d) else None
        c = comp[(comp.cik == cik) & (comp.date >= e0.date)]
        if d0 is not None:
            c = c[c.date <= d0.date + pd.Timedelta(days=20)]
        c0 = c.iloc[-1] if len(c) else None
        later = ga[(ga.date > r.date)]
        rows.append(dict(cik=cik, name=r.name, ann_date=r.date, ann_adsh=r.adsh, ann_fn=r.fn, ann_ftype=r.ftype,
                         ann_items=r.items, sic=r.sic, inc=r.inc, biz=r.biz,
                         entry_form=e0.form, entry_date=e0.date, entry_path=e0.path,
                         n_entry_docs=len(e), delist_form=None if d0 is None else d0.form,
                         delist_date=pd.NaT if d0 is None else d0.date,
                         comp_adsh=None if c0 is None else c0.adsh, comp_fn=None if c0 is None else c0.fn,
                         comp_date=pd.NaT if c0 is None else c0.date,
                         n_later_101=int(((later.date > e0.date) & ((d0 is None) or True)).sum()),
                         later_101_dates=",".join(later.date.dt.strftime("%Y-%m-%d"))))
        # the episode occupies the target until delisting (or 3 years if never delisted)
        busy_until = d0.date if d0 is not None else e0.date + pd.Timedelta(days=1095)
df = pd.DataFrame(rows)
df["year"] = df.ann_date.dt.year
df["days_to_delist"] = (df.delist_date - df.entry_date).dt.days
df.to_parquet(DATA / "deals_raw.parquet")
print(len(df), df.cik.nunique())
print(df.groupby("year").size())
print(df.entry_form.value_counts())
print(df.days_to_delist.describe())
print((df.days_to_delist.isna()).groupby(df.year).mean().round(2))
