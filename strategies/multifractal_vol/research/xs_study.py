"""Cross-sectional industry allocations driven by vol forecasts / trading time."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/user/alpha/strategies/multifractal_vol/research")
from bt import evaluate, DATA
import wf

IND = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]
H = 21
R = DATA.returns
lr = np.log1p(R)
dates = R.index
month_start = pd.Series(dates.month, index=dates).diff().fillna(1) != 0


def monthly(w):
    w = w.copy()
    w.loc[~month_start.values] = np.nan
    return w


def tt_mom(fc, L=252, skip=21):
    """Drift per unit trading time: sum r / sum sigma^2 over [t-L, t-skip]."""
    dvar = fc / H  # ex-ante daily variance (clock time -> trading time increments)
    num = lr.rolling(L - skip).sum().shift(skip)
    den = dvar.shift(1).rolling(L - skip).sum().shift(skip)
    return num / den


def tt_z(fc, L=252, skip=21):
    """Trading-time z-score: sum r / sqrt(sum sigma^2)."""
    dvar = fc / H
    num = lr.rolling(L - skip).sum().shift(skip)
    den = dvar.shift(1).rolling(L - skip).sum().shift(skip)
    return num / np.sqrt(den)


def clock_mom(L=252, skip=21):
    return lr.rolling(L - skip).sum().shift(skip)


def topk(score, k=4, weights=None):
    s = score[IND]
    rk = s.rank(axis=1, ascending=False)
    sel = (rk <= k).astype(float)
    if weights is not None:
        sel = sel * weights[IND]
    sel = sel.div(sel.sum(axis=1), axis=0)
    return sel


if __name__ == "__main__":
    which = sys.argv[1:]
    mrw = wf.get("mrw")
    ewm = wf.get("ewma")
    vol = np.sqrt(mrw)
    if "base" in which:
        evaluate(monthly(pd.DataFrame(1 / 12, index=dates, columns=IND)), "EW industries monthly")
        iv = (1 / vol[IND]).div((1 / vol[IND]).sum(axis=1), axis=0)
        evaluate(monthly(iv), "inverse-vol industries (MRW)")
        pv = vol[IND].div(vol[IND].sum(axis=1), axis=0)
        evaluate(monthly(pv), "vol-proportional industries (MRW)")
    if "mom" in which:
        evaluate(monthly(topk(clock_mom(), 4)), "clock 12-1 mom top4 EW")
        evaluate(monthly(topk(tt_mom(mrw), 4)), "tt-drift 12-1 (MRW clock) top4 EW")
        evaluate(monthly(topk(tt_z(mrw), 4)), "tt-z 12-1 (MRW clock) top4 EW")
