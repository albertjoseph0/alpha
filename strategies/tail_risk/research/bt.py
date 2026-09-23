"""Research helper: score a causally computed weight panel with the harness engine.

Weights must be computed with rolling/expanding operations only (row d uses data <= d).
Uses harness.engine.simulate, so lag / costs / gross cap are identical to the harness.
Every call to `score` is one dev evaluation; calls are appended to evals.log.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import json
import pathlib
import numpy as np
import pandas as pd

from harness import load_dev, WINDOWS, ASSETS, INDUSTRIES
from harness.engine import simulate

HERE = pathlib.Path(__file__).resolve().parent
LOG = HERE / "evals.log"
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        _DATA = load_dev()
    return _DATA


def score(W: pd.DataFrame, tag: str = "", log: bool = True, windows=("dev", "dev_a", "dev_b")):
    d = data()
    W = W.reindex(index=d.dates, columns=ASSETS)
    out = {}
    for w in windows:
        s, e = WINDOWS[w]
        res = simulate(W, d, s, e)
        out[w] = res.cagr
    # extra diagnostics on dev
    s, e = WINDOWS["dev"]
    res = simulate(W, d, s, e)
    eq = res.equity
    dd = (eq / eq.cummax() - 1).min()
    Wd = W.loc[s:e].fillna(0.0)
    out["avg_gross"] = float(Wd.abs().sum(axis=1).mean())
    out["maxdd"] = float(dd)
    lr = np.log(eq).diff().dropna()
    out["vol"] = float(lr.std() * np.sqrt(252))
    if log:
        with open(LOG, "a") as f:
            f.write(json.dumps({"tag": tag, **{k: round(v, 5) for k, v in out.items()}}) + "\n")
    return out


def fmt(o):
    return (f"dev {o['dev']:+.2%}  a {o['dev_a']:+.2%}  b {o['dev_b']:+.2%}  "
            f"gross {o['avg_gross']:.2f}  vol {o['vol']:.1%}  mdd {o['maxdd']:.1%}")
