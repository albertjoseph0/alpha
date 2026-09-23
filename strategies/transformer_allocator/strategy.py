"""End-to-end transformer allocator (see README.md).

A small factorised (time x asset) transformer reads multi-horizon, vol-normalised tokens of
all 13 assets and outputs long-only weights over the 13 assets + cash (softmax). It is
trained to maximise the mean log growth (= in-sample CAGR) of the weekly-rebalanced
portfolio with the harness's 1-day execution lag and 5 bp costs. The ensemble has 4 members,
each early-stopped on a different time-ordered fold. Refit every 3 years on all history.
Weights change only on the first trading day of each week (other rows = hold / drift).
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd
import torch

from harness import ASSETS, MarketData, Strategy

import ta_core as T

torch.set_num_threads(1)

CFG = dict(model="transformer", d=16, heads=2, layers=1, ff=32, drop=0.1, lr=2e-3, wd=0.1,
           epochs=30, patience=6, chunk=26, chunks_per_batch=16, members=4, purge=2)
WEEK_SIGN = False   # no signed return from the last 5 days (stale-price / lead-lag guard)


class TransformerAllocator(Strategy):
    name = "transformer:alloc_axial_ens4_noweeksign"
    refit_every = 756

    def __init__(self, cfg=None):
        self.cfg = dict(CFG if cfg is None else cfg)
        self.models = None

    def fit(self, data: MarketData) -> None:
        R = data.returns[ASSETS].to_numpy(dtype=float)
        rf = data.rf.to_numpy(dtype=float)
        F = T.features(R, week_sign=WEEK_SIGN)
        reb = T.rebalance_mask(data.dates)
        seed = int(data.last_date.strftime("%Y%m%d"))
        self.models, self.info = T.fit_ensemble(F, R, rf, reb, len(R) - 1, self.cfg, seed)

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        # Only the tail is needed: LOOKBACK rows before the first requested date (+ margin).
        pos = data.dates.get_indexer(dates)
        lo = max(0, int(pos.min()) - T.LOOKBACK - 5)
        R = data.returns[ASSETS].to_numpy(dtype=float)[lo:]
        F = T.features(R, week_sign=WEEK_SIGN)
        reb = T.rebalance_mask(data.dates[max(0, lo - 1):])[1 if lo > 0 else 0:]
        out = np.full((len(dates), len(ASSETS)), np.nan)
        rel = pos - lo
        use = reb[rel] & ~np.isnan(F[rel]).any(axis=(1, 2, 3))
        if use.any():
            out[use] = T.ensemble_weights(self.models, F[rel[use]])[:, :len(ASSETS)]
        return pd.DataFrame(out, index=dates, columns=ASSETS)
