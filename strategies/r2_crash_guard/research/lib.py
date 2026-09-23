"""Fast research loop: monthly decisions -> harness.engine.simulate (identical frictions)."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
from harness import I49, WINDOWS
from harness.data import load
from harness.engine import simulate

DATA = load(until="1999-12-31")
R = DATA.tradeable_returns()
COLS = list(R.columns)
RI = R[I49]
LP = np.log1p(RI.fillna(0)).cumsum()
VALID = RI.notna().rolling(252).sum() >= 250
LPM = np.log1p(R["Mkt"]).cumsum()
cal = DATA.dates
FIRST = cal[1:][cal[1:].month != cal[:-1].month]          # first trading day of each month
N_CONFIGS = 0

def mom(lb=252, skip=21):
    return LP.shift(skip) - LP.shift(lb)

def run_weights(fn, windows=("dev_a", "dev_b", "early")):
    """fn(d) -> pd.Series of weights over COLS. Returns {window: SimResult}."""
    global N_CONFIGS; N_CONFIGS += 1
    dec = pd.DataFrame(np.nan, index=cal, columns=COLS)
    for d in FIRST:
        if d < pd.Timestamp("1927-07-15"): continue
        w = fn(d)
        dec.loc[d] = 0.0; dec.loc[d, w.index] = w.values
    out = {}
    for win in windows:
        s, e = WINDOWS[win]
        out[win] = simulate(dec, DATA, s, e)
    return out

def bh(windows=("dev_a", "dev_b", "early")):
    return run_weights(lambda d: pd.Series({"Mkt": 1.0}), windows)

def top_third(m_row, frac=1/3):
    k = max(1, int(round(len(m_row) * frac)))
    top = m_row.nlargest(k).index
    return pd.Series(1.0 / k, index=top)
