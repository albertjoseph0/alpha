"""Portfolio-construction experiments (industries), monthly rebalance, trailing windows only."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from bt import data, score, fmt
from harness import INDUSTRIES, ASSETS

d = data()
R = d.returns
I = R[INDUSTRIES]
dates = R.index
prev_m = pd.Series(dates.month, index=dates).shift(1)
rebal = dates[(dates.month != prev_m.to_numpy())]
rebal = rebal[rebal >= pd.Timestamp("1949-11-01")]


def min_cvar(X, beta=0.95, mu=None, lam=0.0, wmax=1.0):
    """Rockafellar-Uryasev LP: min CVaR_beta(-Xw) - lam*mu'w, w>=0, sum w = 1."""
    T, n = X.shape
    # vars: w (n), a (1), u (T)
    c = np.concatenate([np.zeros(n), [1.0], np.full(T, 1.0 / ((1 - beta) * T))])
    if mu is not None and lam:
        c[:n] -= lam * mu
    # u_t >= -X_t w - a  ->  -X_t w - a - u_t <= 0
    A = np.hstack([-X, -np.ones((T, 1)), -np.eye(T)])
    b = np.zeros(T)
    Aeq = np.concatenate([np.ones(n), [0.0], np.zeros(T)])[None, :]
    bounds = [(0, wmax)] * n + [(None, None)] + [(0, None)] * T
    res = linprog(c, A_ub=A, b_ub=b, A_eq=Aeq, b_eq=[1.0], bounds=bounds, method="highs")
    return res.x[:n]


def build(fn, win):
    W = pd.DataFrame(np.nan, index=dates, columns=ASSETS)
    for t in rebal:
        k = dates.get_loc(t)
        X = I.iloc[max(0, k - win + 1):k + 1]
        w = fn(X, k)
        W.loc[t, INDUSTRIES] = w
        W.loc[t, "Mkt"] = 0.0
    return W


def ew(X, k):
    return np.full(12, 1 / 12)


def invvol(X, k, p=1.0):
    v = X.std().to_numpy()
    w = v ** -p
    return w / w.sum()


def tailparity(X, k, mu_tail=3.0, q=0.05):
    # Bouchaud et al. 1998 for independent power-law tails: w_i ∝ A_i^{-mu/(mu-1)}; A_i ~ ES_q
    Xn = X.to_numpy()
    es = np.array([-np.mean(np.sort(c)[:max(5, int(q * len(c)))]) for c in Xn.T])
    w = es ** (-mu_tail / (mu_tail - 1))
    return w / w.sum()


def mincvar(X, k, beta=0.95):
    return min_cvar(X.to_numpy(), beta)


exps = {
    "ew_monthly": (ew, 756),
    "invvol_3y": (invvol, 756),
    "tailparity_mu3_3y": (tailparity, 756),
    "mincvar95_5y": (mincvar, 1260),
}
which = sys.argv[1:] or list(exps)
for name in [w for w in which if w in exps]:
    fn, win = exps[name]
    W = build(fn, win)
    o = score(W, "port:" + name)
    wavg = W[INDUSTRIES].loc["1950":].dropna().mean()
    print(f"{name:24s} {fmt(o)}")
    print("   avg w:", " ".join(f"{c}:{wavg[c]:.2f}" for c in INDUSTRIES))


# ---- generalized efficiency frontier variants: return axis = 12-1 momentum ----
def mom_scores(k):
    p = (1 + I.iloc[k - 251:k - 20]).prod().to_numpy()
    return p


def mom_top_ew(X, k, n=6):
    s = mom_scores(k)
    idx = np.argsort(-s)[:n]
    w = np.zeros(12); w[idx] = 1 / n
    return w


def mom_top_mincvar(X, k, n=6, beta=0.95):
    s = mom_scores(k)
    idx = np.argsort(-s)[:n]
    w = np.zeros(12)
    w[idx] = min_cvar(X.to_numpy()[:, idx], beta)
    return w


exps.update({
    "mom_top6_ew": (mom_top_ew, 756),
    "mom_top6_mincvar95_5y": (mom_top_mincvar, 1260),
    "mom_top4_ew": (lambda X, k: mom_top_ew(X, k, 4), 756),
})
if __name__ == "__main__" and sys.argv[1:] and sys.argv[1] in ("mom_top6_ew", "mom_top6_mincvar95_5y", "mom_top4_ew"):
    for name in sys.argv[1:]:
        fn, win = exps[name]
        W = build(fn, win)
        o = score(W, "port:" + name)
        wavg = W[INDUSTRIES].loc["1950":].dropna().mean()
        print(f"{name:24s} {fmt(o)}")
        print("   avg w:", " ".join(f"{c}:{wavg[c]:.2f}" for c in INDUSTRIES))
