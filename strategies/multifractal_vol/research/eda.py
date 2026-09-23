"""Exploratory: does forecast volatility predict subsequent risk-adjusted returns?

Buckets days by a simple causal EWMA vol and reports the annualised mean excess
return, vol and Sharpe of the market over the following 21 days (starting t+2,
matching the harness execution lag). Also prints industry CAGRs.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/alpha")
from harness import load_dev, INDUSTRIES

d = load_dev()
R = d.returns
rf = d.rf
ex = R["Mkt"] - rf
lr = np.log1p(R["Mkt"])

ewma = (lr ** 2).ewm(alpha=0.06, adjust=False).mean()
vol = np.sqrt(252 * ewma)

H = 21
fwd = ex[::-1].rolling(H).sum()[::-1].shift(-2)  # excess return over t+2..t+22
fwd_var = (lr ** 2)[::-1].rolling(H).sum()[::-1].shift(-2)

df = pd.DataFrame({"vol": vol, "fwd": fwd, "fwdv": fwd_var}).dropna()
for per, (a, b) in {"1926-49": ("1927", "1949"), "1950-74": ("1950", "1974"),
                    "1975-99": ("1975", "1999")}.items():
    x = df.loc[a:b].copy()
    x["q"] = pd.qcut(x["vol"], 5, labels=False)
    g = x.groupby("q").agg(vol=("vol", "mean"), mu=("fwd", "mean"), rv=("fwdv", "mean"))
    g["mu_ann"] = g["mu"] * 252 / H
    g["rv_ann"] = np.sqrt(g["rv"] * 252 / H)
    g["sharpe"] = g["mu_ann"] / g["rv_ann"]
    g["kelly"] = g["mu_ann"] / g["rv_ann"] ** 2
    print(per)
    print(g[["vol", "mu_ann", "rv_ann", "sharpe", "kelly"]].round(3))

print("\nIndustry CAGR (arith, vol) 1950-1999:")
for c in ["Mkt"] + INDUSTRIES:
    x = R[c].loc["1950":"1999"]
    cagr = np.exp(np.log1p(x).sum() / 50) - 1
    print(f"{c:6s} {cagr:.4f} {x.mean()*252:.4f} {x.std()*np.sqrt(252):.4f}")
for per in [("1950", "1974"), ("1975", "1999")]:
    x = R.loc[per[0]:per[1]]
    cg = np.exp(np.log1p(x).sum() / 25) - 1
    print(per, cg.round(3).to_dict())
