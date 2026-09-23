"""Exploration: what is predictable at the execution-matched horizon (t+2 .. t+h+1)?"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
from harness import load_dev

d = load_dev()
lr = np.log1p(d.returns)
m = lr["Mkt"]
h = 5
# forward tradable h-day return: sum r_{t+2..t+h+1}
fwd = m.rolling(h).sum().shift(-(h + 1))
# trailing vol (EWMA-ish via rolling 63d)
vol = m.rolling(63).std()
volL = m.rolling(504).std()
z_fwd = fwd / (vol * np.sqrt(h))
past = m.rolling(h).sum()
z_past = past / (vol * np.sqrt(h))
df = pd.DataFrame({"fwd": fwd, "zf": z_fwd, "zp": z_past, "vol": vol, "vr": vol / volL,
                   "mom252": m.rolling(252).sum(), "dd": m.rolling(252).sum()}).dropna()
for per, (a, b) in {"1927-49": ("1927", "1949"), "1950-74": ("1950", "1974"), "1975-99": ("1975", "1999")}.items():
    x = df.loc[a:b]
    print(per, "corr(zp, zf)=%.3f" % x[["zp", "zf"]].corr().iloc[0, 1],
          " corr(|zp|,|zf|)=%.3f" % np.corrcoef(x.zp.abs(), x.zf.abs())[0, 1])
    # forward annualised mean & std by vol quintile
    q = pd.qcut(x.vol, 5, labels=False)
    g = x.groupby(q).fwd.agg(["mean", "std"])
    g["mean"] *= 252 / h; g["std"] *= np.sqrt(252 / h)
    g["kelly"] = g["mean"] / g["std"] ** 2
    print(" by trailing-vol quintile:\n", g.round(3).T.to_string())
    q = pd.qcut(x.vr, 5, labels=False)
    g = x.groupby(q).fwd.agg(["mean", "std"])
    g["mean"] *= 252 / h; g["std"] *= np.sqrt(252 / h)
    print(" by vol-ratio (63d/504d) quintile:\n", g.round(3).T.to_string())
    q = pd.qcut(x.mom252, 5, labels=False)
    g = x.groupby(q).fwd.agg(["mean", "std"])
    g["mean"] *= 252 / h; g["std"] *= np.sqrt(252 / h)
    print(" by 12m momentum quintile:\n", g.round(3).T.to_string())

# lag autocorrelations of daily returns by decade
for dec in range(1930, 2000, 10):
    x = m.loc[str(dec):str(dec + 9)]
    print(dec, "ac1=%.3f ac2=%.3f" % (x.autocorr(1), x.autocorr(2)))
