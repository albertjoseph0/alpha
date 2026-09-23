"""Fast local re-implementation of the harness engine for research (dev data only).
Mirrors harness.engine: decision at t earns from t+2, 5bp turnover cost vs drifted weights,
cash earns RF. Used only for quick exploration; official numbers come from the harness CLI."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/user/alpha")
from harness import load_dev, ASSETS

WIN = {"dev": ("1950-01-01", "1999-12-31"), "dev_a": ("1950-01-01", "1974-12-31"),
       "dev_b": ("1975-01-01", "1999-12-31")}


def sim(W: pd.DataFrame, data, window="dev", cost=5e-4):
    """W: decisions indexed by decision date (full calendar ok), columns subset of ASSETS."""
    s, e = WIN[window]
    cal = data.dates
    k0 = cal.searchsorted(pd.Timestamp(s)); kN = cal.searchsorted(pd.Timestamp(e), side="right") - 1
    need = cal[k0 - 2: kN - 1]
    dec = W.reindex(index=need, columns=ASSETS)
    hold = dec.isna().all(axis=1).to_numpy()
    Wm = dec.fillna(0.0).to_numpy()
    R = data.returns[ASSETS].iloc[k0:kN + 1].to_numpy(); RF = data.rf.iloc[k0:kN + 1].to_numpy()
    eq = 1.0; h = np.zeros(len(ASSETS)); curve = np.empty(len(R))
    for i in range(len(R)):
        t = h if hold[i] else Wm[i]
        g = np.abs(t).sum()
        if g > 1 + 1e-9: t = t / g
        eq *= 1 - cost * np.abs(t - h).sum()
        p = t @ R[i] + (1 - t.sum()) * RF[i]
        eq *= 1 + p; curve[i] = eq
        h = t * (1 + R[i]) / (1 + p)
    yrs = (cal[kN] - cal[k0 - 1]).days / 365.25
    return eq ** (1 / yrs) - 1, pd.Series(curve, index=cal[k0:kN + 1])
