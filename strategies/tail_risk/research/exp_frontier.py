"""Generalized efficiency frontier experiments: momentum return axis x CVaR tail axis."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
from bt import data, score, fmt
from harness import INDUSTRIES, ASSETS
from tails import frontier_weights, cvar, min_cvar_weights

d = data()
R = d.returns
I = R[INDUSTRIES]
m = R["Mkt"]
dates = R.index
prev_m = pd.Series(dates.month, index=dates).shift(1)
rebal = dates[(dates.month != prev_m.to_numpy())]
rebal = rebal[rebal >= pd.Timestamp("1949-11-01")]
In = I.to_numpy()
mn = m.to_numpy()


def mom_rank(k, look=252, skip=21):
    p = np.prod(1 + In[k - look + 1:k - skip + 1], axis=0)
    r = np.argsort(np.argsort(p))  # 0..11
    return (r - 5.5) / 5.5


def run(name, win=1260, beta=0.95, wmax=0.25, cap_mult=1.0, cap_ref="mkt"):
    W = pd.DataFrame(np.nan, index=dates, columns=ASSETS)
    for t in rebal:
        k = dates.get_loc(t)
        X = In[k - win + 1:k + 1]
        s = mom_rank(k)
        if cap_ref == "mkt":
            cap = cap_mult * cvar(mn[k - win + 1:k + 1], beta)
        else:
            cap = np.inf
        w = frontier_weights(X, s, cap, beta, wmax)
        W.loc[t, INDUSTRIES] = w
        W.loc[t, "Mkt"] = 0.0
    o = score(W, "frontier:" + name)
    wavg = W[INDUSTRIES].loc["1950":].dropna().mean()
    print(f"{name:28s} {fmt(o)}", flush=True)
    print("   avg w:", " ".join(f"{c}:{wavg[c]:.2f}" for c in INDUSTRIES), flush=True)
    return W


if __name__ == "__main__":
    which = sys.argv[1:]
    if "nocap" in which:
        run("mom_rank_lp_nocap_w25", cap_ref="none")
    if "cap1" in which:
        run("mom_frontier_cvar_le_mkt_w25", cap_mult=1.0)
