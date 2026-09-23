"""Research helpers: evaluate a full causal weight matrix with the harness engine.

Weights are computed for every date with trailing-only features, then scored by
harness.engine.simulate (identical frictions: 1-day lag, 5bp, gross cap, cash RF).
Every call to `evaluate` counts as one dev evaluation and is logged to evals.log.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/alpha")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness import load_dev  # noqa: E402
from harness.data import ASSETS, INDUSTRIES, WINDOWS  # noqa: E402
from harness.engine import simulate  # noqa: E402

DATA = load_dev()
LOG = os.path.join(os.path.dirname(__file__), "evals.log")


PRE = (pd.Timestamp("1935-01-01"), pd.Timestamp("1949-12-31"))  # pre-dev check (inside load_dev)


def evaluate(W: pd.DataFrame, label: str, windows=("dev", "dev_a", "dev_b"), log=True, pre=False):
    W = W.reindex(index=DATA.dates, columns=ASSETS)
    out = {}
    for w in windows:
        s, e = WINDOWS[w]
        res = simulate(W, DATA, s, e)
        out[w] = res.cagr
    if pre:
        out["pre"] = simulate(W, DATA, *PRE).cagr
        label = label + f"  [pre35-49 {out['pre']:+.2%}]"
    # turnover diagnostic over dev
    ww = W.loc["1950":].ffill().fillna(0.0)
    to = ww.diff().abs().sum(1).mean() * 252
    avg_gross = ww.abs().sum(1).mean()
    out["turnover"] = to
    out["gross"] = avg_gross
    line = f"{label:<48s} dev {out.get('dev', np.nan):+.2%}  a {out.get('dev_a', np.nan):+.2%}  b {out.get('dev_b', np.nan):+.2%}  TO {to:5.1f}/y  gross {avg_gross:.2f}"
    print(line, flush=True)
    if log:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    return out


def monthly_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """True on the first trading day of each month (causal: compares with the previous date)."""
    m = index.month.to_numpy()
    mask = np.ones(len(index), dtype=bool)
    mask[1:] = m[1:] != m[:-1]
    return mask


def weekly_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """True on the first trading day of each ISO week (causal)."""
    wk = index.isocalendar().week.to_numpy()
    mask = np.ones(len(index), dtype=bool)
    mask[1:] = wk[1:] != wk[:-1]
    return mask


def hold_between(W: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
    """Keep rows on rebalance days; NaN (hold/drift) on the others."""
    W = W.copy()
    W.loc[~mask] = np.nan
    return W
