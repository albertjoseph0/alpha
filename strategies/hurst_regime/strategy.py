"""fractal:hurst_xs_persistence -- Joseph effect on RELATIVE industry returns.

Every 21 trading days (anchored at the first row of the data, so the schedule is
identical for truncated data):
  1. Relative weekly log returns  x_i = industry_i - Mkt  (5-day blocks anchored at row 0).
  2. Pooled persistence H* = mean over the 12 industries of the average of three
     Hurst estimators (Anis-Lloyd-corrected R/S, DFA-1, variance-time) on the last
     520 completed weeks (10 years) of x_i.   (Mandelbrot: "never publish any result
     based on a single tool", book p. 220.)
  3. If H* > 0.5 (cross-sectional relative performance is persistent): hold the 4
     industries with the highest trailing 252-day relative log return, 1/4 each.
     Otherwise (no persistence -> trends are not to be trusted): equal-weight the
     12 industries.
Targets are held (re-targeted daily to the same weights) until the next anchor.
See README.md for the research behind these choices.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hurst import dfa_hurst, rs_hurst, vt_hurst  # noqa: E402

from harness import ASSETS, MarketData, Strategy  # noqa: E402

IND = ASSETS[1:]
ANCHOR = 21          # rebalance cadence (trading days)
WEEK = 5             # block length for weekly returns
H_WEEKS = 520        # 10-year window for the pooled H estimate
MOM_DAYS = 252       # 12-month relative strength
TOP_K = 4
H_THRESHOLD = 0.5    # Brownian value: no free parameter


def _h3(x: np.ndarray) -> float:
    return float(np.mean([
        rs_hurst(x, [13, 26, 52, 65, 130, 260]),
        dfa_hurst(x, [8, 13, 26, 52]),
        vt_hurst(x, [2, 4, 8, 13, 26]),
    ]))


def _weights_at(lr: np.ndarray, p: int) -> np.ndarray:
    """Target weights (len 13, ASSETS order) using log returns rows 0..p only."""
    w = np.zeros(len(ASSETS))
    ew = np.zeros(len(ASSETS))
    ew[1:] = 1.0 / len(IND)
    t = (p + 1) // WEEK                      # completed weekly blocks
    if t < H_WEEKS or p + 1 < MOM_DAYS + 1:
        return ew
    rel = lr[: t * WEEK, 1:] - lr[: t * WEEK, [0]]
    wk = rel[(t - H_WEEKS) * WEEK:].reshape(H_WEEKS, WEEK, len(IND)).sum(axis=1)
    h_pooled = np.mean([_h3(wk[:, j]) for j in range(len(IND))])
    if not np.isfinite(h_pooled) or h_pooled <= H_THRESHOLD:
        return ew
    seg = lr[p + 1 - MOM_DAYS: p + 1]
    rel12 = seg[:, 1:].sum(axis=0) - seg[:, 0].sum()
    top = np.argsort(-rel12, kind="stable")[:TOP_K]
    w[1 + top] = 1.0 / TOP_K
    return w


class HurstXSPersistence(Strategy):
    name = "fractal:hurst_xs_persistence"
    refit_every = None  # nothing is learned; all state is computed causally in predict

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        lr = np.log1p(data.returns[ASSETS].to_numpy(dtype=float))
        pos = data.dates.get_indexer(dates)
        if (pos < 0).any():
            raise ValueError("requested dates not in data")
        # last anchor row <= p: anchors are rows with (row % ANCHOR) == ANCHOR - 1
        anc = pos - ((pos - (ANCHOR - 1)) % ANCHOR)
        out = np.zeros((len(dates), len(ASSETS)))
        cache: dict[int, np.ndarray] = {}
        for i, a in enumerate(anc):
            if a < 0:
                out[i, 1:] = 1.0 / len(IND)
                continue
            if a not in cache:
                cache[a] = _weights_at(lr, int(a))
            out[i] = cache[a]
        return pd.DataFrame(out, index=dates, columns=ASSETS)
