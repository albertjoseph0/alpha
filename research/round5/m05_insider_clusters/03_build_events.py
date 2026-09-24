"""Build insider-cluster purchase events from the SEC Form 4 data sets.

Event definition (all information dated by SEC FILING date, never transaction date):
  * open-market purchase = Form 4 (original, not 4/A), non-derivative, code P, acquired (A),
    shares > 0, price > 0, not preferred/notes/warrants/rights.
  * insider = reporting owner that is an Officer or Director (pure 10% holders / "Other" excluded,
    they are mostly funds). Joint filings are collapsed to one insider (lowest owner CIK).
  * On each filing date F for issuer i: count distinct insiders with a purchase whose
    transaction date is within [F-30d, F] and whose filing date is <= F.  The first F where the
    count reaches >= 3 is an event. After an event the issuer cannot trigger again for 182 days.
  * Entry is decided later (04/05 scripts): next trading day's close after F.

Also computes per-event features for the literature filters:
  * n_opp: insiders in the cluster that are NOT routine (Cohen-Malloy-Pomorski: routine = traded
    (P or S) in the same calendar month in each of the 3 prior calendar years; classified at the
    start of each year from trades FILED before that year; unclassifiable before 2009 -> not routine)
  * med_pct_hold: median across cluster insiders of shares bought / shares held before (capped)
  * has_ceo_cfo: any cluster insider with CEO/CFO/Chief Executive/Chief Financial in title
  * dollars: total $ bought by cluster insiders in the window
"""
import glob, re, json
import numpy as np, pandas as pd

D = "/home/user/alpha/data/round5/m05_insider_clusters"
WIN = 30
COOLDOWN = 182
MIN_INS = 3

files = sorted(f for f in glob.glob(f"{D}/quarters/*.parquet") if "_trail" not in f)
cols = ["accession_number", "security_title", "trans_date", "trans_code", "trans_shares",
        "trans_pricepershare", "trans_acquired_disp_cd", "shrs_ownd_folwng_trans", "filing_date",
        "document_type", "issuercik", "issuername", "issuertradingsymbol", "owner_cik",
        "owner_name", "relationship", "title"]
df = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
df = df[df.document_type == "4"]
df["issuercik"] = df.issuercik.astype(str).str.lstrip("0")
df["owner_cik"] = df.owner_cik.astype(str).str.lstrip("0")
print("P/S rows", len(df), "filing dates", df.filing_date.min(), df.filing_date.max())

# ---------------- routine classification (CMP 2012) ----------------
ps = df[["owner_cik", "issuercik", "trans_date", "filing_date"]].dropna().copy()
ps["y"] = ps.trans_date.dt.year; ps["m"] = ps.trans_date.dt.month
ps["fy"] = ps.filing_date.dt.year
# only trades filed in the same or next year as they happened (a trade filed late in a later
# year would be known only then; to be safe require filing year == trade year)
ps = ps[ps.fy == ps.y]
ym = ps.drop_duplicates(["owner_cik", "issuercik", "y", "m"])[["owner_cik", "issuercik", "y", "m"]]
s = set(map(tuple, ym.values))
routine = set()  # (owner, issuer, year)
for (o, i, y, m) in ym.itertuples(index=False):
    # if traded in month m of years y, y+1, y+2 -> routine in year y+3
    if (o, i, y + 1, m) in s and (o, i, y + 2, m) in s:
        routine.add((o, i, y + 3))
print("routine insider-years", len(routine))

# ---------------- purchases ----------------
p = df[(df.trans_code == "P") & (df.trans_acquired_disp_cd == "A")].copy()
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
print("clean insider purchases", len(p), "issuers", p.issuercik.nunique())

# ---------------- cluster detection ----------------
events = []
for cik, g in p.groupby("issuercik", sort=False):
    fds = np.sort(g.filing_date.unique())
    if g.owner_cik.nunique() < MIN_INS:
        continue
    last_ev = None
    gv = g.sort_values("filing_date")
    for F in fds:
        F = pd.Timestamp(F)
        if last_ev is not None and (F - last_ev).days < COOLDOWN:
            continue
        w = gv[(gv.filing_date <= F) & (gv.trans_date >= F - pd.Timedelta(days=WIN))]
        ins = w.owner_cik.unique()
        if len(ins) < MIN_INS:
            continue
        # only trigger if a filing ON F contributes (otherwise it triggered earlier)
        last_ev = F
        per_ins = w.groupby("owner_cik").agg(pct=("pct_hold", "sum"), routine=("routine", "max"),
                                             ceo=("ceo_cfo", "max"), val=("value", "sum"),
                                             off=("is_off", "max"))
        wf = w[w.filing_date == F]
        events.append(dict(
            cik=cik, fdate=F, name=wf.issuername.iloc[-1], sym=wf.sym.iloc[-1],
            n_ins=len(ins), n_opp=int((~per_ins.routine).sum()), n_off=int(per_ins.off.sum()),
            has_ceo_cfo=bool(per_ins.ceo.any()), med_pct_hold=float(per_ins.pct.median()),
            dollars=float(per_ins.val.sum()), first_tdate=w.trans_date.min(),
            vwap=float(w.value.sum() / w.trans_shares.sum()),
            last_px=float(wf.trans_pricepershare.iloc[-1]),
        ))
ev = pd.DataFrame(events).sort_values("fdate").reset_index(drop=True)
print("events", len(ev))
print(ev.groupby(ev.fdate.dt.year).size().to_string())
ev.to_parquet(f"{D}/events.parquet", index=False)
# purchase-level file for price validation (reported prices)
p[["issuercik", "trans_date", "filing_date", "trans_pricepershare", "sym"]].to_parquet(
    f"{D}/purchases_px.parquet", index=False)
