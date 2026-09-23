"""Exploration 6: re-check the main candidates on 1935-1949 (pre-dev, inside load_dev)."""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, evaluate, monthly_mask, weekly_mask, hold_between, ASSETS, INDUSTRIES  # noqa: E402
import mfcore as mf  # noqa: E402

R = DATA.log_returns()
idx = DATA.dates
mm = monthly_mask(idx)
RI = R[INDUSTRIES]


def to_W(wi):
    W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
    W[INDUSTRIES] = wi.to_numpy()
    return hold_between(W, mm)


def topk(score, k=4):
    rk = score.rank(axis=1, ascending=False, method="first")
    w = (rk <= k).astype(float) / k
    w[score.isna().any(axis=1)] = 1.0 / 12
    return w


def trailing_pct(s, q, n=2520, minp=1260):
    return s.rolling(n, min_periods=minp).quantile(q)


W = pd.DataFrame(0.0, index=idx, columns=ASSETS); W["Mkt"] = 1.0
evaluate(W, "B&H Mkt", pre=True)
evaluate(to_W(pd.DataFrame(1 / 12, index=idx, columns=INDUSTRIES)), "EW industries", pre=True)
mom = RI.rolling(231).sum().shift(21)
eff_d = RI.rolling(252).sum() / RI.abs().rolling(252).sum()
Lw = RI.rolling(5).sum().abs().rolling(250).sum() / 5.0
eff_w = RI.rolling(250).sum() / Lw
evaluate(to_W(topk(mom)), "mom12_1 top4", pre=True)
evaluate(to_W(topk(eff_d)), "eff (daily ruler) top4", pre=True)
evaluate(to_W(topk(eff_w)), "eff (weekly ruler) top4", pre=True)

r = R["Mkt"].to_numpy()
turb = {"rv": np.log(mf.rolling_vol(r, 63)),
        "lam_cov": mf.lambda2_logcov(r, 504),
        "lam_zeta": mf.zeta_curvature(r, 504, qs=(0.5, 1.0, 1.5, 2.0))[0]}
for k, v in turb.items():
    s = pd.Series(v, index=idx)
    hot = (s > trailing_pct(s, 0.8)).to_numpy()
    w = topk(eff_w)
    w.loc[hot] = 1.0 / 12
    evaluate(to_W(w), f"eff_w top4, EW when {k} hot", pre=True)
    # market timing version
    Wm = pd.DataFrame(0.0, index=idx, columns=ASSETS)
    Wm["Mkt"] = (~hot).astype(float)
    evaluate(hold_between(Wm, weekly_mask(idx)), f"Mkt, cash when {k} hot", pre=True)
