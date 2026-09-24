"""DEV-only grid (1990-01 -> 2007-12) over the three free parameters, base pricing + stresses."""
import itertools
import sys

import numpy as np
import pandas as pd

import model as M

START, END = "1990-01-01", "2007-12-31"
df = M.load_data()
b = M.benchmarks(df, START, END)
spy = M.stats(b.spy, b.rf)
tsp = M.stats(b.trend_spy, b.rf)
print("SPY", spy, "\ntrend SPY", tsp)

variants = {
    "base": (M.Pricer("model"), 0.02),
    "2xcost": (M.Pricer("model"), 0.04),
    "vol+2": (M.Pricer("model", vol_bump=0.02), 0.02),
    "vol+4": (M.Pricer("model", vol_bump=0.04), 0.02),
}
rows = []
for X, m, R in itertools.product((0.1, 0.2, 0.3), (1.0, 1.05, 1.10), (1, 3, 6, 12)):
    rec = dict(X=X, m=m, R=R)
    for name, (pr, c) in variants.items():
        res, tr = M.backtest(df, START, END, X=X, m=m, R=R, cost=c, pricer=pr)
        s = M.stats(res.ret, b.rf)
        rec[f"cagr_{name}"] = s["cagr"]
        if name == "base":
            rec.update(vol=s["vol"], sharpe=s["sharpe"], maxdd=s["maxdd"], ntrades=len(tr),
                       beta=M.beta(res.ret, b.spy), avg_optw=res.optw.mean(),
                       cost_drag=(res.cost / res.nav).mean() * 252,
                       excess_spy=s["cagr"] - spy["cagr"])
    rows.append(rec)
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}, flush=True)
g = pd.DataFrame(rows)
g.to_csv("grid_dev.csv", index=False, float_format="%.5f")
print(g.sort_values("cagr_base", ascending=False).head(10).to_string())
