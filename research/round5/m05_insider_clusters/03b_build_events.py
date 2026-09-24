"""Round 5b: rebuild insider-cluster events over the FULL sample (2006q1-2026q1) with purchase-level
footnote text kept for the Jev step. Writes NEW files only (the old events.parquet is left alone):
  events_v2.parquet          one row per cluster event (same definition/columns as 03_build_events.py)
  purchases_v2.parquet       clean officer/director open-market purchases incl. footnotes/remarks (pid index)
  event_members_v2.parquet   (ev, pid) purchases that form each event's cluster window

Event definition (unchanged from 03, all dated by SEC FILING date):
  * purchase = Form 4 (original), non-derivative, code P, acquired, shares>0, price>0, common-type
    security; reporting owner is an Officer or Director; joint filings collapsed to lowest owner CIK.
  * On each filing date F of issuer i: distinct insiders with a purchase with trans date in [F-30d, F]
    and filing date <= F. First F with >= 3 insiders = event; 182-day cooldown per issuer.
  * routine (Cohen-Malloy-Pomorski 2012): insider traded (P or S) the issuer in the same calendar month
    in each of the 3 prior calendar years (trades counted only if filed in the year they happened).
    Data start 2006 -> nobody can be routine before 2009 (then n_opp == n_ins).
"""
import glob, re
import numpy as np, pandas as pd

D = "/home/user/alpha/data/round5/m05_insider_clusters"
WIN, COOLDOWN, MIN_INS = 30, 182, 3

mains = sorted(f for f in glob.glob(f"{D}/quarters/*q?.parquet"))
ps = pd.concat([pd.read_parquet(f, columns=["owner_cik", "issuercik", "trans_date", "filing_date",
                                             "document_type"]) for f in mains], ignore_index=True)
ps = ps[ps.document_type == "4"].dropna()
for c in ["owner_cik", "issuercik"]:
    ps[c] = ps[c].astype(str).str.lstrip("0")
ps["y"] = ps.trans_date.dt.year; ps["m"] = ps.trans_date.dt.month
ps = ps[ps.filing_date.dt.year == ps.y]
ym = ps.drop_duplicates(["owner_cik", "issuercik", "y", "m"])[["owner_cik", "issuercik", "y", "m"]]
s = set(map(tuple, ym.values))
routine = {(o, i, y + 3) for (o, i, y, m) in s if (o, i, y + 1, m) in s and (o, i, y + 2, m) in s}
print("P/S rows", len(ps), "routine insider-years", len(routine), flush=True)
del ps, ym, s

pf = sorted(glob.glob(f"{D}/quarters/*_pfn.parquet"))
p = pd.concat([pd.read_parquet(f) for f in pf], ignore_index=True)
p = p[p.document_type == "4"]
for c in ["owner_cik", "issuercik"]:
    p[c] = p[c].astype(str).str.lstrip("0")
p = p[p.trans_acquired_disp_cd == "A"]
bad = re.compile(r"prefer|note|debenture|warrant|right|option|bond|pfd", re.I)
p = p[~p.security_title.fillna("").str.contains(bad)]
p = p[(p.trans_shares > 0) & (p.trans_pricepershare > 0)]
rel = p.relationship.fillna("")
p["is_off"] = rel.str.contains("Officer"); p["is_dir"] = rel.str.contains("Director")
p = p[p.is_off | p.is_dir]
p = p[p.trans_date.notna() & p.filing_date.notna()]
p = p[(p.trans_date <= p.filing_date) & (p.trans_date >= p.filing_date - pd.Timedelta(days=365))]
p["value"] = p.trans_shares * p.trans_pricepershare
before = p.shrs_ownd_folwng_trans - p.trans_shares
p["pct_hold"] = np.where(before > 0, p.trans_shares / before.where(before > 0), 10.0)
p["pct_hold"] = p.pct_hold.clip(upper=10.0)
p["routine"] = [(o, i, y) in routine for o, i, y in zip(p.owner_cik, p.issuercik, p.trans_date.dt.year)]
t = p.title.fillna("")
p["ceo_cfo"] = t.str.contains(r"CEO|C\.E\.O|Chief Exec|CFO|C\.F\.O|Chief Fin", case=False, regex=True)
p["sym"] = p.issuertradingsymbol.fillna("").str.upper().str.strip()
p = p.sort_values(["filing_date", "accession_number", "nonderiv_trans_sk"]).reset_index(drop=True)
p.index.name = "pid"
print("clean insider purchases", len(p), "issuers", p.issuercik.nunique(),
      "dates", p.filing_date.min().date(), p.filing_date.max().date(), flush=True)
p.to_parquet(f"{D}/purchases_v2.parquet")

events, members = [], []
for cik, g in p.groupby("issuercik", sort=False):
    if g.owner_cik.nunique() < MIN_INS:
        continue
    last_ev = None
    for F in np.sort(g.filing_date.unique()):
        F = pd.Timestamp(F)
        if last_ev is not None and (F - last_ev).days < COOLDOWN:
            continue
        w = g[(g.filing_date <= F) & (g.trans_date >= F - pd.Timedelta(days=WIN))]
        ins = w.owner_cik.unique()
        if len(ins) < MIN_INS:
            continue
        wf = w[w.filing_date == F]
        if len(wf) == 0:   # no filing on F contributes: stale cluster (seen before, blocked by cooldown)
            continue
        last_ev = F
        per_ins = w.groupby("owner_cik").agg(pct=("pct_hold", "sum"), routine=("routine", "max"),
                                             ceo=("ceo_cfo", "max"), val=("value", "sum"), off=("is_off", "max"))
        k = len(events)
        events.append(dict(
            cik=cik, fdate=F, name=wf.issuername.iloc[-1], sym=wf.sym.iloc[-1],
            n_ins=len(ins), n_opp=int((~per_ins.routine).sum()), n_off=int(per_ins.off.sum()),
            has_ceo_cfo=bool(per_ins.ceo.any()), med_pct_hold=float(per_ins.pct.median()),
            dollars=float(per_ins.val.sum()), first_tdate=w.trans_date.min(),
            vwap=float(w.value.sum() / w.trans_shares.sum()),
            last_px=float(wf.trans_pricepershare.iloc[-1])))
        members += [(k, pid) for pid in w.index]
ev = pd.DataFrame(events)
order = ev.sort_values(["fdate", "cik"]).index
remap = {old: new for new, old in enumerate(order)}
ev = ev.loc[order].reset_index(drop=True); ev.index.name = "ev"
mem = pd.DataFrame(members, columns=["ev", "pid"]); mem["ev"] = mem.ev.map(remap)
print("events", len(ev))
print(ev.groupby(ev.fdate.dt.year).size().to_string())
ev.to_parquet(f"{D}/events_v2.parquet")
mem.to_parquet(f"{D}/event_members_v2.parquet", index=False)
