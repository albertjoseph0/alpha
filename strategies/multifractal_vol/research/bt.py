"""Fast research backtests: causal weight frames -> harness.engine.simulate.

Uses exactly the harness engine (lag, costs, gross cap) but skips the
walk-forward/causality audit; weights passed in must already be causal.
Every call to `evaluate` is counted in COUNTER_FILE (dev evaluations).
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/alpha")
from harness import load_dev, ASSETS, WINDOWS
from harness.engine import simulate

DATA = load_dev()
COUNTER_FILE = os.path.join(os.path.dirname(__file__), "eval_count.json")


def _bump(label):
    try:
        with open(COUNTER_FILE) as f:
            c = json.load(f)
    except Exception:
        c = {"n": 0, "labels": []}
    c["n"] += 1
    c["labels"].append(label)
    with open(COUNTER_FILE, "w") as f:
        json.dump(c, f, indent=0)


def evaluate(w: pd.DataFrame, label: str = "", quiet: bool = False) -> dict:
    w = w.reindex(columns=ASSETS).reindex(DATA.dates)
    # before the first valid decision: fully in market (only a couple of days)
    first = w.dropna(how="all").index[0]
    w.loc[w.index < first, :] = 0.0
    w.loc[w.index < first, "Mkt"] = 1.0
    # all-NaN rows = hold (engine semantics); partial NaN = 0
    allnan = w.isna().all(axis=1)
    w.loc[~allnan] = w.loc[~allnan].fillna(0.0)
    out = {"label": label}
    for win in ["dev", "dev_a", "dev_b"]:
        s, e = WINDOWS[win]
        r = simulate(w.loc[:e], DATA, s, e)
        out[win] = r.cagr
        if win == "dev":
            out["equity"] = r.equity
    wd = w.loc["1950":"1999"].ffill().fillna(0.0)
    out["gross"] = float(wd.abs().sum(axis=1).mean())
    out["turn"] = float(wd.diff().abs().sum(axis=1).mean() * 252)
    _bump(label)
    if not quiet:
        print(f"{label:40s} dev {out['dev']:+.2%}  a {out['dev_a']:+.2%}  b {out['dev_b']:+.2%}  "
              f"gross {out['gross']:.2f}  turn/yr {out['turn']:.1f}", flush=True)
    return out
