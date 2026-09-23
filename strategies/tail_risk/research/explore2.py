"""Predictive content of candidate tail / shock signals vs plain realized vol.

For each signal (computed causally at close t), report the annualised mean excess
return and Sharpe of the market over days t+2 .. t+1+H, by signal quintile.
Quintile breakpoints are computed within each period (descriptive only).
Periods: 1927-49 (pre-dev history), 1950-74 (dev_a), 1975-99 (dev_b).
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import pandas as pd
from bt import data
from harness import INDUSTRIES

d = data()
R = d.returns
rf = d.rf
m = R["Mkt"]
ex = m - rf
lm = np.log1p(m)

H = 21
# forward excess return, days t+2..t+1+H
fwd = ex[::-1].rolling(H).sum()[::-1].shift(-2)
fwdv = (m ** 2)[::-1].rolling(H).mean()[::-1].shift(-2) ** 0.5 * np.sqrt(252)

sig = {}
rv21 = m.rolling(21).std() * np.sqrt(252)
rv63 = m.rolling(63).std() * np.sqrt(252)
rv252 = m.rolling(252).std() * np.sqrt(252)
sig["rv21"] = rv21
sig["rv63"] = rv63
# multi-scale shock index (Richter-like): mean log2 ratio of vol at scales vs 5y baseline
base = m.rolling(1260, min_periods=500).std() * np.sqrt(252)
sig["shock"] = sum(np.log2(v / base) for v in (m.rolling(5).std() * np.sqrt(252), rv21, rv63, rv252)) / 4
sig["burst21_252"] = np.log(rv21 / rv252)
# downside share of variance
dn = (m.clip(upper=0) ** 2).rolling(63).sum()
sig["down_share63"] = dn / (m ** 2).rolling(63).sum()
# Noah events: count of |z|>3 in last 63d, z vs lagged 252d vol
z = m / (m.rolling(252).std().shift(1))
sig["noah63"] = (z < -3).astype(float).rolling(63).sum()


# rolling Hill left tail over 504 days, k=25
def roll_hill(x, win=504, k=25):
    a = x.to_numpy()
    out = np.full(len(a), np.nan)
    for i in range(win, len(a) + 1, 5):
        w = -a[i - win:i]
        w = np.sort(w[w > 0])[::-1]
        if len(w) > k:
            out[i - 1] = 1.0 / np.mean(np.log(w[:k] / w[k]))
    return pd.Series(out, index=x.index).ffill()


sig["hill_left504"] = -roll_hill(m)  # negative so that high = fat tail
# standardise residual for tail on vol-filtered series
sig["hill_left_z504"] = -roll_hill(z.fillna(0))

# co-crash breadth: fraction of industries in their own lower 10% (vs lagged 252d rolling quantile)
I = R[INDUSTRIES]
zi = I / I.rolling(252).std().shift(1)
thr = -1.28
cc = (zi < thr).sum(axis=1)
sig["cocrash63"] = (cc >= 9).astype(float).rolling(63).sum()
# pairwise lower-tail dependence proxy: mean co-exceedance / individual exceedance over 252d
ind_ex = (zi < thr).astype(float)
n_ex = ind_ex.sum(axis=1)
sig["taildep252"] = (n_ex * (n_ex - 1)).rolling(252).sum() / ((n_ex * 11).rolling(252).sum() + 1e-9)
# average pairwise correlation 63d (plain dependence)
def avg_corr(Ix, win=63):
    zz = Ix
    v = zz.rolling(win).var()
    tot = zz.sum(axis=1).rolling(win).var()
    s = v.sum(axis=1)
    n = Ix.shape[1]
    return (tot - s) / ((np.sqrt(v).sum(axis=1)) ** 2 - s)
sig["avgcorr63"] = avg_corr(I)
# drawdown from 252d high & trend
px = (1 + m).cumprod()
sig["dd252"] = -(px / px.rolling(252).max() - 1)
sig["trend252"] = -np.log(px / px.shift(252))  # negative trend = high value

periods = [("1927", "1949"), ("1950", "1974"), ("1975", "1999")]
for name, s in sig.items():
    print(f"--- {name} (high quintile = 5)")
    for a, b in periods:
        df = pd.DataFrame({"s": s, "f": fwd, "v": fwdv}).loc[a:b].dropna()
        q = pd.qcut(df["s"].rank(method="first"), 5, labels=False) + 1
        g = df.groupby(q)
        mu = g["f"].mean() * 252 / H
        vo = g["v"].mean()
        line = "  ".join(f"{mu[i]:+.1%}/{vo[i]:.0%}" for i in range(1, 6))
        print(f"  {a}-{b}: exret/fvol by quintile: {line}")
