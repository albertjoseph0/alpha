"""Exploration 7: structural variants of the fractal path-roughness industry core.

V1  eff_w252 top4                         (signed ruler ratio, weekly ruler, 1y)
V2  avg rank of eff_w over 126d and 252d  (two outer rulers)
V3  divider dimension D from the slope of ln L(eps) vs ln eps, eps in 5..252 days,
    score = sign(X_252) * (2 - D)   (the literal ruler method; magnitude-free)
V4  eff_w252 top4, inverse-vol weights within the top 4
V5  eff_w252 top6 equal weight (less concentrated)
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, evaluate, monthly_mask, hold_between, ASSETS, INDUSTRIES  # noqa: E402

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


def ruler_len(eps: int, win: int) -> pd.DataFrame:
    """Average over the eps phases of the path length measured with an eps-day ruler
    over the trailing `win` days (win multiple of eps)."""
    return RI.rolling(eps).sum().abs().rolling(win - eps + 1).sum() / eps


def eff(win, eps=5):
    return RI.rolling(win).sum() / ruler_len(eps, win)


e252 = eff(250)
e126 = eff(125)
evaluate(to_W(topk(e252)), "V1 eff_w252 top4", pre=True)
evaluate(to_W(topk(e252.rank(axis=1) + e126.rank(axis=1))), "V2 eff_w 126+252 rank-avg top4", pre=True)

eps_list = [5, 10, 21, 42, 63, 126, 252]
lnL = np.stack([np.log(ruler_len(e, 252).to_numpy()) for e in eps_list])
x = np.log(np.array(eps_list, float)); xc = x - x.mean()
slope = np.tensordot(xc, lnL, axes=(0, 0)) / (xc ** 2).sum()
D = pd.DataFrame(1.0 - slope, index=idx, columns=INDUSTRIES)
X = RI.rolling(252).sum()
print("median divider D 1950-99:", round(float(np.nanmedian(D.loc['1950':].to_numpy())), 3))
evaluate(to_W(topk(np.sign(X) * (2.0 - D))), "V3 sign(X)*(2-D) divider-dim top4", pre=True)

w = topk(e252)
iv = 1.0 / np.sqrt((RI ** 2).rolling(252).mean())
wv = (w > 0) * iv
wv = wv.div(wv.sum(1), axis=0).where(~e252.isna().any(axis=1), 1.0 / 12, axis=0)
evaluate(to_W(wv), "V4 eff_w252 top4 inv-vol weights", pre=True)
evaluate(to_W(topk(e252, 6)), "V5 eff_w252 top6", pre=True)
