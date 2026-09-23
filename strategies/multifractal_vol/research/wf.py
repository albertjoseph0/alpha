"""Walk-forward per-asset variance forecasts (annual refits), cached to scratchpad."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/alpha/strategies/multifractal_vol")
sys.path.insert(0, "/home/user/alpha/strategies/multifractal_vol/research")
import mfvol as mv
from bt import DATA

SP = "/tmp/claude-0/-home-user-alpha/98ea3775-9ac1-5aa8-9c82-12ae31cc8668/scratchpad/"
H = 21


def refit_points(dates, first_year=1949, step_years=1):
    idx = [int(dates.searchsorted(pd.Timestamp(f"{y}-12-01"))) for y in range(first_year, 2000, step_years)]
    return idx + [len(dates)]


def mrw_wf(lr, dates, L=1000):
    n = len(lr)
    out = np.full(n, np.nan)
    pts = refit_points(dates)
    for a, b in zip(pts[:-1], pts[1:]):
        tr = lr[:a + 1]
        ttr = mv.fwd_rv(tr, H)
        y = mv.logabs(tr)
        lam2, T = mv.mrw_logcov_fit(y)
        T = float(np.clip(T, 60, 5000))
        w = mv.mrw_weights(lam2, T, L, H)
        mu = y.mean()
        s_all = mv.mrw_signal(mv.logabs(lr[:b]), w, mu)
        s_tr = s_all[:a + 1]
        ok = np.isfinite(ttr) & np.isfinite(s_tr)
        c = np.log(np.mean(ttr[ok] / np.exp(2 * s_tr[ok])))
        out[a:b] = np.exp(c + 2 * s_all)[a:b]
    return out


def har_wf(lr, dates):
    n = len(lr)
    out = np.full(n, np.nan)
    pts = refit_points(dates)
    ks = [1, 5, 21, 63, 252]
    X = np.vstack([np.log(mv.past_rv(lr, k) + 1e-10) for k in ks]).T
    X1 = np.c_[np.ones(n), X]
    for a, b in zip(pts[:-1], pts[1:]):
        ttr = mv.fwd_rv(lr[:a + 1], H)
        ok = np.isfinite(ttr) & np.all(np.isfinite(X1[:a + 1]), axis=1)
        coef, *_ = np.linalg.lstsq(X1[:a + 1][ok], np.log(ttr[ok]), rcond=None)
        res = np.log(ttr[ok]) - X1[:a + 1][ok] @ coef
        out[a:b] = np.exp(X1[a:b] @ coef + 0.5 * res.var())
    return out


def get(model="mrw"):
    path = SP + f"wf_{model}.pkl"
    if os.path.exists(path):
        return pd.read_pickle(path)
    R = DATA.returns
    lrs = np.log1p(R)
    res = {}
    for c in R.columns:
        lr = lrs[c].to_numpy()
        if model == "mrw":
            res[c] = mrw_wf(lr, R.index)
        elif model == "har":
            res[c] = har_wf(lr, R.index)
        elif model == "ewma":
            res[c] = H * mv.ewma_var(lr)
    df = pd.DataFrame(res, index=R.index)
    df.to_pickle(path)
    return df


if __name__ == "__main__":
    for m in sys.argv[1:]:
        df = get(m)
        print(m, np.sqrt(df.loc["1950":] * 252 / H).mean().round(3).to_dict())
