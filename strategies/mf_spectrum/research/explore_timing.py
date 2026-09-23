"""Exploration 3: market timing with MF turbulence filters vs a plain RV filter.

Pre-registered rules (one shot each; thresholds = 80th/20th pct of the feature's
own trailing 10-year history, so no level is fitted):
  R1 RV-only      : cash when ln RV63 > trailing 80th pct
  R2 lam_cov      : cash when lambda2 (log-vol cov, 504d) > trailing 80th pct
  R2z lam_zeta    : cash when lambda2 (zeta curvature, q<=2, 504d) > trailing 80th pct
  R3 RV & lam_cov : cash when both
  R4 Hoelder      : cash when local Hoelder alpha < trailing 20th pct (activity burst)
  R5 trend & MF   : long when 200d trend up OR lam_cov below its trailing median
Decisions are taken weekly (first trading day of the week).
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import DATA, evaluate, weekly_mask, hold_between, ASSETS  # noqa: E402
import mfcore as mf  # noqa: E402

R = DATA.log_returns()
idx = DATA.dates
r = R["Mkt"].to_numpy()
wk = weekly_mask(idx)

f = pd.DataFrame(index=idx)
f["lnrv63"] = np.log(mf.rolling_vol(r, 63))
f["lam_cov"] = mf.lambda2_logcov(r, 504)
lz, _ = mf.zeta_curvature(r, 504, qs=(0.5, 1.0, 1.5, 2.0))
f["lam_zeta"] = lz
f["holder"] = mf.holder_local(r)
f["trend"] = pd.Series(r, index=idx).rolling(200).sum()


def trailing_pct(s: pd.Series, q: float, n: int = 2520, minp: int = 1260) -> pd.Series:
    return s.rolling(n, min_periods=minp).quantile(q)


def run(expo: pd.Series, label: str):
    W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
    W["Mkt"] = expo.fillna(1.0).astype(float)
    return evaluate(hold_between(W, wk), label)


hi_rv = f["lnrv63"] > trailing_pct(f["lnrv63"], 0.8)
hi_lc = f["lam_cov"] > trailing_pct(f["lam_cov"], 0.8)
hi_lz = f["lam_zeta"] > trailing_pct(f["lam_zeta"], 0.8)
lo_h = f["holder"] < trailing_pct(f["holder"], 0.2)
med_lc = f["lam_cov"] < trailing_pct(f["lam_cov"], 0.5)

run(~hi_rv, "R1 RV63 filter")
run(~hi_lc, "R2 lam_cov filter")
run(~hi_lz, "R2z lam_zeta(q<=2) filter")
run(~(hi_rv & hi_lc), "R3 RV & lam_cov filter")
run(~lo_h, "R4 Hoelder-burst filter")
run((f["trend"] > 0) | med_lc, "R5 trend OR calm-cascade")
print("fraction of dev time out of market:",
      {k: round(float(v.loc['1950':].mean()), 2) for k, v in
       dict(rv=hi_rv, lc=hi_lc, lz=hi_lz, both=hi_rv & hi_lc, h=lo_h).items()})
