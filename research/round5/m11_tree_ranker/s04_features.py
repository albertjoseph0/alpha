"""Monthly feature panel + labels.

Timing: features at the close of the LAST trading day of month m (formation f, index i); trade at
the close of the next trading day (t0 = i+1); hold to the close of the first trading day of the
following month (t1). Label = holding-period return from t0 close to t1 close.

Universe at f: S&P 500 PIT members (m11 rebuild) U S&P 400 PIT members (m01) at the month end.
Eligible = price at f and >= 245 valid closes in the last 253 days (a rule known at f). Members
with no price at all at f are the survivorship hole; they are counted per month (n_nodata) and
handled by imputation scenarios in the backtest.

Output: DATA/panel.parquet (one row per formation month x eligible ticker), DATA/months.csv."""
from common import *

C = pd.read_pickle(DATA / "close.pkl")
V = pd.read_pickle(DATA / "volume.pkl")
spy = C["SPY"].dropna()
cal = spy.index
C = C.reindex(cal).astype("float64")
V = V.reindex(cal).astype("float64")
R = C.pct_change(fill_method=None)
DV = C * V

M5 = pd.read_csv(DATA / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M4 = pd.read_csv(M01 / "membership_monthly.csv", parse_dates=["month_end"])
MEM5 = {me.to_period("M"): set(g.ticker) for me, g in M5.groupby("month_end")}
MEM4 = {me.to_period("M"): set(g.ticker) for me, g in M4.groupby("month_end")}

# FINRA monthly short ratio
fin = {}
for f in sorted((DATA / "finra").glob("*.csv")):
    a = pd.read_csv(f, index_col=0)
    fin[pd.Period(f.stem)] = (a["short"] / a["total"]).where(a["total"] > 0)
SR = pd.DataFrame(fin).T.sort_index()  # period x ticker

ym = cal.to_period("M")
last_idx = pd.Series(np.arange(len(cal)), index=cal).groupby(ym).max().values
ETF = [e for e in SECTOR_ETFS if e in C.columns]

rows, mrows = [], []
for k, i in enumerate(last_idx):
    f = cal[i]
    per = f.to_period("M")
    if per < pd.Period("2011-12") or i < 260:
        continue
    m5, m4 = MEM5.get(per, set()), MEM4.get(per, set())
    mem = {t for t in (m5 | m4) if "#" not in t}
    n_ph = len([t for t in (m5 | m4) if "#" in t])
    if not mem:
        continue
    has_t1 = k + 1 < len(last_idx) and i + 1 < len(cal)
    t0 = i + 1 if i + 1 < len(cal) else None
    t1 = last_idx[k + 1] + 1 if k + 1 < len(last_idx) and last_idx[k + 1] + 1 < len(cal) else None
    cols = [t for t in mem if t in C.columns]
    px = C[cols].iloc[i]
    win = C[cols].iloc[i - 252:i + 1]
    nvalid = win.notna().sum()
    elig = px.notna() & (nvalid >= 245)
    nodata = len(mem) - int(px.notna().sum())
    el = list(px.index[elig])
    mrows.append(dict(form=f, per=str(per), t0=cal[t0] if t0 else pd.NaT, t1=cal[t1] if t1 else pd.NaT,
                      n_mem=len(mem) + n_ph, n_elig=len(el), n_nodata=nodata + n_ph,
                      n_short=int((px.notna() & ~elig).sum()),
                      n_nodata5=len([t for t in m5 if "#" in t or t not in C.columns or pd.isna(C[t].iloc[i])]),
                      n_mem5=len(m5)))
    P = C[el].iloc[i - 252:i + 1].ffill()
    r = R[el].iloc[i - 251:i + 1].fillna(0.0)  # 252 daily returns ending at f
    d = pd.DataFrame(index=el)
    d["mom12_1"] = P.iloc[-22] / P.iloc[0] - 1
    d["mom6_1"] = P.iloc[-22] / P.iloc[-127] - 1
    d["rev1"] = P.iloc[-1] / P.iloc[-22] - 1
    d["hi52"] = P.iloc[-1] / P.max()
    d["vol1"] = r.iloc[-21:].std()
    d["vol12"] = r.std()
    d["maxret1"] = r.iloc[-21:].max()
    # market model and sector-residual model (daily, 252d)
    s = R["SPY"].iloc[i - 251:i + 1].fillna(0.0).values
    sc = s - s.mean()
    rv = r.values
    rc = rv - rv.mean(0)
    beta = sc @ rc / (sc @ sc)
    e1 = rc - np.outer(sc, beta)
    E = R[ETF].iloc[i - 251:i + 1].fillna(0.0).values
    Ec = E - E.mean(0)
    Eb = sc @ Ec / (sc @ sc)
    Ee = Ec - np.outer(sc, Eb)  # sector ETF residuals vs SPY
    corr = (Ee / np.linalg.norm(Ee, axis=0)).T @ (e1 / (np.linalg.norm(e1, axis=0) + 1e-12))  # 9 x n
    best = corr.argmax(0)
    Eb_sel = Ee[:, best]
    gam = (Eb_sel * e1).sum(0) / (Eb_sel * Eb_sel).sum(0)
    e2 = e1 - Eb_sel * gam
    d["beta"] = beta
    d["ivol"] = e2.std(0)
    d["resmom"] = e2[:-21].sum(0) / (e2[:-21].std(0) * np.sqrt(len(e2) - 21) + 1e-12)
    ep = C[ETF].iloc[i - 252:i + 1]
    secmom = (ep.iloc[-22] / ep.iloc[0] - 1).values
    d["secmom"] = secmom[best]
    d["sector"] = np.array(ETF)[best]
    dv = DV[el].iloc[i - 251:i + 1]
    d["size_dv"] = np.log(dv.median() + 1)
    d["dv_trend"] = np.log((dv.iloc[-21:].mean() + 1) / (dv.mean() + 1))
    am = (R[el].iloc[i - 62:i + 1].abs() / DV[el].iloc[i - 62:i + 1].replace(0, np.nan)).mean()
    d["amihud"] = np.log(am * 1e9 + 1e-6)
    d["logprice"] = np.log(P.iloc[-1])
    sr = SR.loc[per].reindex(el) if per in SR.index else pd.Series(np.nan, index=el)
    pp = per - 3
    sr3 = SR.loc[pp].reindex(el) if pp in SR.index else pd.Series(np.nan, index=el)
    d["short_ratio"] = sr.values
    d["short_chg"] = (sr - sr3).values
    d["is500"] = [1.0 if t in m5 else 0.0 for t in el]
    # label: holding-period return t0 close -> t1 close (exit at last available price if series ends)
    if t0 is not None and t1 is not None:
        pe = C[el].iloc[t0]
        w2 = C[el].iloc[t0:t1 + 1]
        lastpx = w2.ffill().iloc[-1]
        d["ret"] = (lastpx / pe - 1).values
        d["ended"] = w2.iloc[-1].isna().values & pe.notna().values  # series stops inside holding window
        d["spy_ret"] = C["SPY"].iloc[t1] / C["SPY"].iloc[t0] - 1
    else:
        d["ret"] = np.nan; d["ended"] = False; d["spy_ret"] = np.nan
    d["form"] = f
    d.index.name = "ticker"
    rows.append(d.reset_index())
    if k % 12 == 0:
        print(per, len(mem), len(el), nodata, flush=True)

panel = pd.concat(rows, ignore_index=True)
panel.to_parquet(DATA / "panel.parquet")
pd.DataFrame(mrows).to_csv(DATA / "months.csv", index=False)
print(panel.shape)
print(panel.describe().T.to_string())
