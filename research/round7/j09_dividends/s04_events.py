"""Events: FTS 8-K dividend hits -> point-in-time S&P 500/400 members -> one event per firm per 30-day cluster
(earliest filing), matched to XBRL quarterly dividends-per-share for the quarter containing the announcement.
Also lists XBRL-detected increases/initiations and whether an 8-K event covers them (coverage report).
-> DATA/events_raw.parquet, DATA/xbrl_changes.parquet"""
import numpy as np
import pandas as pd
from common import DATA

h = pd.read_parquet(DATA / "fts_hits.parquet")
u = pd.read_parquet(DATA / "universe_monthly.parquet").dropna(subset=["cik"])
u["cik"] = u.cik.astype(int)
h = h[h.cik.isin(set(u.cik))].copy()
h["file_date"] = pd.to_datetime(h.file_date)
h["pri"] = np.where(h.file_type.str.startswith("EX-99"), 0, np.where(h.file_type.str.startswith("8-K"), 1, 9))
h = h[h.pri < 9]
grp = h.groupby("adsh").grp.agg(lambda s: ",".join(sorted(set(s))))
best = h.sort_values(["adsh", "pri", "score"], ascending=[True, True, False]).drop_duplicates("adsh")
f = best[["adsh", "cik", "name", "file_date", "file_type", "file", "items"]].copy()
f["groups"] = f.adsh.map(grp)
for g in ("inc", "ini", "spe"):
    f["fts_" + g] = f.groups.str.contains(g).astype(int)

# point-in-time membership: last month-end strictly before the filing date
f["m_asof"] = (f.file_date - pd.offsets.MonthEnd(1))
f.loc[f.file_date.dt.is_month_end, "m_asof"] = f.file_date - pd.offsets.MonthEnd(1)
px = pd.read_pickle(DATA / "px_close_adj.pkl") if (DATA / "px_close_adj.pkl").exists() else None
pxcols = set(px.columns) if px is not None else set()
um = u.rename(columns={"month_end": "m_asof"})
m = f.merge(um, on=["m_asof", "cik"], how="inner")
m["has_px"] = m.ticker.isin(pxcols)
m = m.sort_values(["adsh", "has_px", "ticker"], ascending=[True, False, True]).drop_duplicates("adsh")
print("filings in universe (any time)", f.adsh.nunique(), "PIT members", len(m))

# cluster: earliest filing per cik within 30 days
m = m.sort_values(["cik", "file_date"])
keep, last = [], {}
for r in m.itertuples():
    lk = last.get(r.cik)
    if lk is not None and (r.file_date - lk).days <= 30:
        keep.append(False)
        continue
    keep.append(True)
    last[r.cik] = r.file_date
m = m[keep].copy()

# XBRL match: quarter containing the announcement (use file_date - 1 day: filings often trail the release)
q = pd.read_parquet(DATA / "dps_quarterly.parquet").sort_values(["cik", "qend"])
qg = {c: g.reset_index(drop=True) for c, g in q.groupby("cik")}
cols = {k: [] for k in ["x_new", "x_old", "x_prev4", "x_nprev4", "x_hist", "x_ninc12", "x_qend", "x_filedata"]}
for r in m.itertuples():
    g = qg.get(r.cik)
    d = r.file_date - pd.Timedelta(days=1)
    vals = dict(x_new=np.nan, x_old=np.nan, x_prev4=np.nan, x_nprev4=0, x_hist=0, x_ninc12=np.nan, x_qend=pd.NaT,
                x_filedata=int(g is not None))
    if g is not None:
        i = g.index[(g.qstart <= d) & (g.qend >= d)]
        if len(i):
            i = i[0]
            qs = g.qstart[i]
            vals["x_new"] = g.dps[i]
            vals["x_qend"] = g.qend[i]
            prev = g[(g.qend < qs) & (g.qend >= qs - pd.Timedelta(days=372))]
            vals["x_prev4"] = prev.dps.sum()
            vals["x_nprev4"] = len(prev)
            pos = g[(g.qend < qs) & (g.dps > 0)]
            vals["x_hist"] = int(len(pos) > 0)
            if len(pos) and (qs - pos.qend.iloc[-1]).days <= 200:
                vals["x_old"] = pos.dps.iloc[-1]
            p12 = g[(g.qend < qs) & (g.qend >= qs - pd.Timedelta(days=3 * 365 + 10))].dps.values
            vals["x_ninc12"] = int((np.diff(p12) > 1e-6).sum()) if len(p12) > 1 else np.nan
    for k, v in vals.items():
        cols[k].append(v)
for k, v in cols.items():
    m[k] = v
m["x_chg"] = m.x_new / m.x_old - 1
m["x_ini"] = ((m.x_new > 0) & (m.x_prev4.fillna(0) == 0)).astype(int)
m.to_parquet(DATA / "events_raw.parquet")
m["y"] = m.file_date.dt.year
print("events", len(m), "with px", int(m.has_px.sum()))
print(m.groupby("y").agg(n=("adsh", "size"), px=("has_px", "mean"), inc=("fts_inc", "mean"), ini=("fts_ini", "mean"),
                         spe=("fts_spe", "mean"), xnew=("x_new", lambda s: s.notna().mean()),
                         xup=("x_chg", lambda s: (s > 0.005).mean()), xini=("x_ini", "mean")).round(2).to_string())

# XBRL-detected changes (for coverage): quarter dps > previous positive quarter by >0.5%, or first dividend after >=4
# zero/absent quarters while the firm files XBRL
rows = []
for c, g in qg.items():
    for i in range(1, len(g)):
        new, qs = g.dps[i], g.qstart[i]
        prev = g[(g.qend < qs) & (g.qend >= qs - pd.Timedelta(days=372))]
        pos = g[(g.qend < qs) & (g.dps > 0)]
        old = pos.dps.iloc[-1] if len(pos) and (qs - pos.qend.iloc[-1]).days <= 200 else np.nan
        if new > 0 and prev.dps.sum() == 0 and len(prev) >= 2:
            rows.append((c, qs, g.qend[i], "ini", new, old))
        elif new > 0 and old > 0 and 1.005 < new / old < 3:
            rows.append((c, qs, g.qend[i], "inc", new, old))
x = pd.DataFrame(rows, columns=["cik", "qstart", "qend", "kind", "new", "old"])
ev = m[["cik", "x_qend"]].dropna().assign(hit=1).drop_duplicates()
x = x.merge(ev.rename(columns={"x_qend": "qend"}), on=["cik", "qend"], how="left").fillna({"hit": 0})
x.to_parquet(DATA / "xbrl_changes.parquet")
x["y"] = x.qend.dt.year
print("XBRL changes (all universe CIKs, any time) by year and share with an 8-K FTS event in the same quarter:")
print(x[x.y >= 2012].groupby(["y", "kind"]).hit.agg(["size", "mean"]).unstack().round(2).to_string())
