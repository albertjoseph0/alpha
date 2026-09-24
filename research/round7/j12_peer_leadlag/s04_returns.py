"""Monthly return panel from m11's adjusted closes (read-only).
d_m = last trading day of month m; e_m = next trading day (execution, 1-day lag).
r_sig[m]  = C(d_m)/C(d_{m-1}) - 1                (known at the close of d_m; used for the signal)
r_hold[m] = C(e_{m+1})/C(e_m) - 1                (return of a position formed on month-m info, entered at e_m)
If a price series ends inside the holding window: last available price (trunc=1), stress-tested later.
Also log 63-day average dollar volume at d_m (size proxy), and benchmark holding returns (SPY, RSP, IJH, MDY).
Output: DATA/monthly.parquet, DATA/bench_monthly.parquet"""
from common import *

C = pd.read_pickle(M11 / "close.pkl").astype("float64")
V = pd.read_pickle(M11 / "volume.pkl").astype("float64")
V = V.loc[~V.index.duplicated(), ~V.columns.duplicated()].reindex(index=C.index, columns=C.columns)
B = pd.read_pickle(M01 / "bench_close.pkl").astype("float64")
cal = C.index[C["SPY"].notna()] if "SPY" in C.columns else B.index[B["SPY"].notna()]
C = C.reindex(cal)
V = V.reindex(cal)
B = B.reindex(cal)
dv = (C * V).rolling(63, min_periods=20).mean()
s = pd.Series(cal, index=cal)
d_m = s.groupby(cal.to_period("M")).max()          # last trading day of each month
pos = {d: i for i, d in enumerate(cal)}
d_idx = np.array([pos[d] for d in d_m.values])
e_idx = d_idx + 1
months = d_m.index.to_timestamp("M")
Cv = C.values
n_m = len(months)
rows = []
for k in range(1, n_m - 1):
    if e_idx[k + 1] >= len(cal):
        break
    a, b = d_idx[k - 1], d_idx[k]
    e0, e1 = e_idx[k], e_idx[k + 1]
    r_sig = Cv[b] / Cv[a] - 1
    c0 = Cv[e0]
    seg = Cv[e0:e1 + 1]
    last = pd.DataFrame(seg).ffill().values[-1]
    r_hold = last / c0 - 1
    trunc = np.isfinite(c0) & ~np.isfinite(seg[-1])
    df = pd.DataFrame({"month_end": months[k], "ticker": C.columns, "r_sig": r_sig, "r_hold": r_hold,
                       "trunc": trunc, "ldv": np.log1p(dv.values[b])})
    rows.append(df.dropna(subset=["r_sig", "r_hold"], how="all"))
P = pd.concat(rows, ignore_index=True)
P.to_parquet(DATA / "monthly.parquet", index=False)
bm = []
for k in range(1, n_m - 1):
    if e_idx[k + 1] >= len(cal):
        break
    bm.append({"month_end": months[k], **{t: B[t].values[e_idx[k + 1]] / B[t].values[e_idx[k]] - 1 for t in B.columns}})
pd.DataFrame(bm).to_parquet(DATA / "bench_monthly.parquet", index=False)
print(P.shape, P.month_end.min(), P.month_end.max(), "trunc", int(P.trunc.sum()))
