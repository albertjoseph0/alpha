"""Baseline landscape (a few reference cores) to know what the MF filters are applied to."""
from common import DATA, evaluate, monthly_mask, hold_between, ASSETS, INDUSTRIES
import numpy as np
import pandas as pd

R = DATA.log_returns()
idx = DATA.dates
mm = monthly_mask(idx)

W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W["Mkt"] = 1.0
evaluate(W, "B&H Mkt (sanity)")

px = R["Mkt"].cumsum()
W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W["Mkt"] = (px.diff(200) > 0).astype(float)
evaluate(W, "trend200 Mkt daily (sanity)")

# vol-managed market, capped at 1: target = trailing 10y median of 63d vol
v63 = np.sqrt((R["Mkt"] ** 2).rolling(63).mean())
tgt = v63.rolling(2520, min_periods=1260).median()
W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W["Mkt"] = (tgt / v63).clip(upper=1.0).fillna(1.0)
evaluate(hold_between(W, mm), "volmanaged Mkt (10y median tgt) monthly")

W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W[INDUSTRIES] = 1.0 / 12
evaluate(hold_between(W, mm), "EW industries monthly")

vi = np.sqrt((R[INDUSTRIES] ** 2).rolling(252).mean())
iv = 1 / vi
W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W[INDUSTRIES] = iv.div(iv.sum(1), axis=0).fillna(1 / 12)
evaluate(hold_between(W, mm), "inverse-vol industries monthly")

mom = R[INDUSTRIES].rolling(231).sum().shift(21)
rk = mom.rank(axis=1, ascending=False)
W = pd.DataFrame(0.0, index=idx, columns=ASSETS)
W[INDUSTRIES] = (rk <= 4).astype(float) / 4
evaluate(hold_between(W, mm), "industry mom 12-1 top4 monthly")
