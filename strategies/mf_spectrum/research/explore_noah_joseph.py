"""Exploration 5: Noah/Joseph decomposition of the 12-month industry trend.

Each day is classed 'singular' (Noah: low local Hoelder exponent at the daily
scale, i.e. |r_t| > c * sigma_{t-1}, sigma from a 63-day trailing RMS known before
the day) or 'regular' (Joseph). The trailing 252-day move X splits into
X_noah + X_joseph. Rank ICs vs forward industry excess returns; also the signed
efficiency (ruler ratio) with daily and weekly rulers.
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, INDUSTRIES  # noqa: E402

R = DATA.log_returns()[INDUSTRIES]
idx = R.index
me = np.zeros(len(idx), bool)
me[:-1] = idx.month[1:] != idx.month[:-1]
pos = np.where(me)[0]

sig = np.sqrt((R ** 2).rolling(63).mean()).shift(1)
z = R.abs() / sig
F = {}
F["mom252"] = R.rolling(252).sum()
F["mom12_1"] = R.rolling(231).sum().shift(21)
for c in (2.0, 3.0):
    noah = R.where(z > c, 0.0)
    F[f"noah_c{c:g}"] = noah.rolling(252).sum()
    F[f"joseph_c{c:g}"] = (R - noah).rolling(252).sum()
    F[f"frac_noah_days_c{c:g}"] = (z > c).astype(float).rolling(252).mean()
F["eff_d"] = R.rolling(252).sum() / R.abs().rolling(252).sum()
wk = R.rolling(5).sum()
# weekly ruler: sum of |5-day returns| on a 5-day grid ending today (5 phases averaged)
Lw = wk.abs().rolling(250).sum() / 5.0
F["eff_w"] = R.rolling(250).sum() / Lw
F["joseph_eff_c2"] = F["joseph_c2"] / R.abs().rolling(252).sum()

cr = R.cumsum()
fwd = {}
for h in (21, 63):
    f = (cr.shift(-h) - cr).iloc[pos]
    fwd[h] = f.sub(f.mean(1), axis=0)

periods = [("1931", "1949"), ("1950", "1974"), ("1975", "1999")]
for k, fx in F.items():
    row = f"{k:<22s}"
    for h in (21, 63):
        ic = fx.iloc[pos].rank(axis=1).corrwith(fwd[h].rank(axis=1), axis=1)
        for a, b in periods:
            s = ic.loc[a:b].dropna()
            if h == 63:
                s = s.iloc[::3]
            row += f" {s.mean():+.3f}(t{s.mean()/s.std()*np.sqrt(len(s)):+.1f})"
    print(row)
print("columns: IC21 31-49, 50-74, 75-99 | IC63 31-49, 50-74, 75-99")
c = F["noah_c2"].iloc[pos].rank(axis=1).corrwith(F["joseph_c2"].iloc[pos].rank(axis=1), axis=1).loc["1950":].mean()
print("mean XS rank corr noah_c2 vs joseph_c2 (1950-99):", round(c, 2))
c = F["joseph_c2"].iloc[pos].rank(axis=1).corrwith(F["mom252"].iloc[pos].rank(axis=1), axis=1).loc["1950":].mean()
print("mean XS rank corr joseph_c2 vs mom252 (1950-99):", round(c, 2))
