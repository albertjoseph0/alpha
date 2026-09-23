"""Exploration 2: cross-sectional information of MF features across the 12 industries.

Month-end sampling; Spearman rank IC of each feature vs forward 1-month and
3-month industry excess returns (relative to the cross-sectional mean).
Also IC of each feature within momentum-sorted groups (does it add to momentum?).
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, INDUSTRIES  # noqa: E402
import mfcore as mf  # noqa: E402

R = DATA.log_returns()[INDUSTRIES]
idx = R.index
me_mask = np.zeros(len(idx), bool)
me_mask[:-1] = idx.month[1:] != idx.month[:-1]
me_pos = np.where(me_mask)[0]

feat = {}
for a in INDUSTRIES:
    r = R[a].to_numpy()
    lp = np.cumsum(r)
    d = {}
    d["mom12_1"] = pd.Series(r).rolling(231).sum().shift(21).to_numpy()
    d["vol252"] = np.log(mf.rolling_vol(r, 252))
    d["lam_cov"] = mf.lambda2_logcov(r, 1008)
    lz, h2 = mf.zeta_curvature(r, 1008)
    d["lam_zeta"] = lz
    d["h2"] = h2
    lz5, _ = mf.zeta_curvature(r, 504)
    d["lam_zeta504"] = lz5
    d["holder"] = mf.holder_local(r)
    d["fdim126"] = mf.fractal_dimension(lp, 63)
    d["fdim252"] = mf.fractal_dimension(lp, 126)
    s252 = pd.Series(r).rolling(252).sum().to_numpy()
    a252 = pd.Series(np.abs(r)).rolling(252).sum().to_numpy()
    d["eff252"] = s252 / a252          # trend efficiency (signed)
    # kurtosis of daily returns in last 252 days (non-MF control for tails)
    d["kurt252"] = pd.Series(r).rolling(252).kurt().to_numpy()
    for k, v in d.items():
        feat.setdefault(k, {})[a] = v
F = {k: pd.DataFrame(v, index=idx) for k, v in feat.items()}

cr = R.cumsum()
fwd21 = (cr.shift(-21) - cr).iloc[me_pos]
fwd63 = (cr.shift(-63) - cr).iloc[me_pos]
fwd21 = fwd21.sub(fwd21.mean(1), axis=0)
fwd63 = fwd63.sub(fwd63.mean(1), axis=0)


def ic_series(fx, fy):
    fx = fx.iloc[me_pos] if len(fx) == len(idx) else fx
    return fx.rank(axis=1).corrwith(fy.rank(axis=1), axis=1)


periods = [("1931", "1949"), ("1950", "1974"), ("1975", "1999")]
print(f"{'feature':<12s}" + "".join(f"  IC21 {p[0][2:]}-{p[1][2:]}  " for p in periods) + "".join(f"  IC63 {p[0][2:]}-{p[1][2:]}  " for p in periods))
for k, fx in F.items():
    ic1 = ic_series(fx, fwd21)
    ic3 = ic_series(fx, fwd63)
    row = f"{k:<12s}"
    for (a, b) in periods:
        s = ic1.loc[a:b].dropna()
        row += f"  {s.mean():+.3f} (t{s.mean()/s.std()*np.sqrt(len(s)):+.1f})"
    for (a, b) in periods:
        s = ic3.loc[a:b].dropna().iloc[::3]
        row += f"  {s.mean():+.3f} (t{s.mean()/s.std()*np.sqrt(len(s)):+.1f})"
    print(row)

# average cross-sectional rank correlation between features (1950-99)
print("\nmean cross-sectional rank corr with mom12_1 and vol252 (1950-99):")
for k, fx in F.items():
    c1 = fx.iloc[me_pos].rank(axis=1).corrwith(F["mom12_1"].iloc[me_pos].rank(axis=1), axis=1).loc["1950":].mean()
    c2 = fx.iloc[me_pos].rank(axis=1).corrwith(F["vol252"].iloc[me_pos].rank(axis=1), axis=1).loc["1950":].mean()
    c3 = fx.iloc[me_pos].rank(axis=1).corrwith(F["kurt252"].iloc[me_pos].rank(axis=1), axis=1).loc["1950":].mean()
    print(f"  {k:<12s} mom {c1:+.2f}  vol {c2:+.2f}  kurt {c3:+.2f}")

pd.to_pickle(F, os.path.join(os.path.dirname(__file__), "feats_ind_daily.pkl"))
