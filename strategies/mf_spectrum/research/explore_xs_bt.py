"""Exploration 4: industry cores (momentum vs fractal path-roughness score) and a
turbulence-conditioned concentration switch (RV vs MF turbulence measures).

Always fully invested in industries; monthly rebalancing (first trading day).
Turbulence switch: when the market's turbulence measure is above its trailing
80th percentile, hold all 12 industries equally instead of the top 4.
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, evaluate, monthly_mask, hold_between, ASSETS, INDUSTRIES  # noqa: E402
import mfcore as mf  # noqa: E402

R = DATA.log_returns()
idx = DATA.dates
mm = monthly_mask(idx)
RI = R[INDUSTRIES]

mom = RI.rolling(231).sum().shift(21)
eff = RI.rolling(252).sum() / RI.abs().rolling(252).sum()

r = R["Mkt"].to_numpy()
turb = pd.DataFrame(index=idx)
turb["rv"] = np.log(mf.rolling_vol(r, 63))
turb["lam_cov"] = mf.lambda2_logcov(r, 504)
turb["lam_zeta"] = mf.zeta_curvature(r, 504, qs=(0.5, 1.0, 1.5, 2.0))[0]


def trailing_pct(s, q, n=2520, minp=1260):
    return s.rolling(n, min_periods=minp).quantile(q)


def topk(score: pd.DataFrame, k=4) -> pd.DataFrame:
    rk = score.rank(axis=1, ascending=False, method="first")
    w = (rk <= k).astype(float) / k
    w[score.isna().any(axis=1)] = 1.0 / 12
    return w


def to_W(wi: pd.DataFrame) -> pd.DataFrame:
    W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
    W[INDUSTRIES] = wi.to_numpy()
    return hold_between(W, mm)


cores = {"mom12_1": topk(mom), "eff252": topk(eff)}
for cname, wc in cores.items():
    if cname != "mom12_1":
        evaluate(to_W(wc), f"core {cname} top4")
    for tname in ["rv", "lam_cov", "lam_zeta"]:
        hot = (turb[tname] > trailing_pct(turb[tname], 0.8)).to_numpy()
        w = wc.copy()
        w.loc[hot] = 1.0 / 12
        evaluate(to_W(w), f"core {cname} top4, EW when {tname} hot")
