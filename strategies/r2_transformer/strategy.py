"""r2:transformer_rule49 -- final of the r2 transformer-ranker angle.

The learned set-attention ranker (r2t_core.SetRanker) did not add robust value over plain
12-1 momentum on the 49 industries (it lost dev_a by 1.2-2.5 points; see README.md), so the
honest final is the rule itself: 12-1 momentum, top third of valid industries, equal weight,
rebalanced on the first trading day of each month. The features and the rule share
r2t_core's code path with the walk-forward research (research/wf.py).
"""
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import r2t_core as C
from harness import I49, Strategy


class TransformerRule49(Strategy):
    name = "r2:transformer_rule49"
    refit_every = None          # nothing is learned

    def predict(self, data, dates):
        R = data.extra[I49].to_numpy()
        P = C.Prep(R, data.returns["Mkt"].to_numpy())
        ms = C.month_starts(data.dates)
        pos = data.dates.get_indexer(dates)
        keep = np.array([p >= C.LOOK and ms[p] for p in pos])
        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        if keep.any():
            F, V = C.features(P, pos[keep])
            out.iloc[np.flatnonzero(keep)] = C.rule_weights(F, V)
        return out
