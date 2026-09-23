"""Exploration 1: do rolling multifractal estimates carry information beyond realized vol?

Market (Mkt) only, dev data 1926-1999 via harness.load_dev(). Month-end sampling,
non-overlapping forward windows. Prints partial regressions (HAC-free, but
non-overlapping monthly samples) of forward vol / forward excess returns on each
feature after controlling for log realized vol.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, "/home/user/alpha")
from harness import load_dev  # noqa: E402
import mfcore as mf  # noqa: E402

d = load_dev()
lr = d.log_returns()
rf = np.log1p(d.rf)
r = lr["Mkt"].to_numpy()
idx = lr.index

# full-sample sanity check
om = np.log(np.abs(r) + 1e-4)
for per in [("1926", "1949"), ("1950", "1974"), ("1975", "1999")]:
    m = (idx >= per[0]) & (idx <= per[1] + "-12-31")
    rr = r[m]
    lam_cov = mf.lambda2_logcov(rr, window=len(rr))[-1]
    lam_z, h = mf.zeta_curvature(rr, window=len(rr))
    print(f"full-sample {per}: lambda2(logcov)={lam_cov:.4f}  lambda2(zeta)={lam_z[-1]:.4f}  h={h[-1]:.3f}")

W = 1008
feats = pd.DataFrame(index=idx)
feats["lnrv21"] = np.log(mf.rolling_vol(r, 21))
feats["lnrv252"] = np.log(mf.rolling_vol(r, 252))
feats["lam_cov"] = mf.lambda2_logcov(r, window=W)
lz, hz = mf.zeta_curvature(r, window=W)
feats["lam_zeta"] = lz
feats["h2"] = hz
feats["lam_cov504"] = mf.lambda2_logcov(r, window=504)
lz5, _ = mf.zeta_curvature(r, window=504)
feats["lam_zeta504"] = lz5
feats["holder"] = mf.holder_local(r)
feats["fdim63"] = mf.fractal_dimension(np.cumsum(r), 63)
feats["lam_scale"] = mf.logvol_scale_slope(r, window=W)
feats["vts"] = feats["lnrv252"] - feats["lnrv21"]      # vol term structure (long minus short)

ex = pd.Series(r - rf.to_numpy(), index=idx)
cex = ex.cumsum()
cr2 = pd.Series(r * r, index=idx).cumsum()
# month-end sample dates
me = feats.groupby([idx.year, idx.month]).tail(1).index
pos = idx.get_indexer(me)
H = 21
fwd = {}
ok = pos + H < len(idx)
pos = pos[ok]
me = me[ok]
f = feats.iloc[pos].copy()
f["fwd_lnrv"] = 0.5 * np.log((cr2.iloc[pos + H].to_numpy() - cr2.iloc[pos].to_numpy()) / H)
f["fwd_ex21"] = cex.iloc[pos + H].to_numpy() - cex.iloc[pos].to_numpy()
pos63 = pos[pos + 63 < len(idx)]
f["fwd_ex63"] = np.nan
f.loc[idx[pos63], "fwd_ex63"] = cex.iloc[pos63 + 63].to_numpy() - cex.iloc[pos63].to_numpy()

print("\ncorrelations of features (monthly, 1930-1999):")
cols = ["lnrv21", "lnrv252", "lam_cov", "lam_zeta", "lam_cov504", "lam_zeta504", "lam_scale", "h2", "holder", "fdim63", "vts"]
print(f[cols].loc["1930":].corr().round(2).to_string())


def ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    s2 = e @ e / (len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    return b, b / np.sqrt(np.diag(cov))


print("\npartial t-stats of each feature controlling for lnrv21 (+lnrv252):")
for per in [("1931", "1949"), ("1950", "1974"), ("1975", "1999"), ("1931", "1999")]:
    g = f.loc[per[0]:per[1]]
    line = []
    for tgt in ["fwd_lnrv", "fwd_ex21", "fwd_ex63"]:
        for c in ["lam_cov", "lam_zeta", "lam_scale", "h2", "holder", "fdim63", "vts"]:
            gg = g[["lnrv21", "lnrv252", c, tgt]].dropna()
            if tgt == "fwd_ex63":
                gg = gg.iloc[::3]  # non-overlapping quarters
            b, t = ols(gg[tgt].to_numpy(), gg[["lnrv21", "lnrv252", c]].to_numpy())
            line.append(f"{tgt}|{c}: t={t[3]:+.1f}")
    print(per)
    for k in range(0, len(line), 7):
        print("   ", "  ".join(line[k:k + 7]))

print("\nbaseline: fwd_lnrv on lnrv21, lnrv252 R2 and fwd_ex21 on lnrv21 t-stat")
for per in [("1931", "1949"), ("1950", "1974"), ("1975", "1999")]:
    g = f.loc[per[0]:per[1]].dropna(subset=["lnrv21", "lnrv252", "fwd_lnrv", "fwd_ex21"])
    b, t = ols(g["fwd_lnrv"].to_numpy(), g[["lnrv21", "lnrv252"]].to_numpy())
    b2, t2 = ols(g["fwd_ex21"].to_numpy(), g[["lnrv21"]].to_numpy())
    print(per, "vol coefs", b.round(3), "t", t.round(1), "| ret on lnrv21 t", t2.round(1))

f.to_pickle(os.path.join(os.path.dirname(__file__), "feats_mkt_monthly.pkl"))
