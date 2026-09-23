"""fractal:tails_chiseled_frontier -- Bouchaud-style "tail chiseling" on a generalized efficiency frontier.

Each month (first trading day), over the 12 industries:
  * return axis: cross-sectional rank of 12-1 month momentum (ranks, not raw returns, because
    sample means are unreliable under power-law tails);
  * tail axis: empirical expected shortfall CVaR_95 of the portfolio's daily returns over the
    trailing 5 years (Rockafellar-Uryasev LP);
  * solve  max rank'w  s.t.  CVaR_95(w) <= CVaR_95(market),  sum w = 1,  0 <= w <= 0.25.
The portfolio is the highest-momentum mix whose historical crash severity (its joint left
tail, including co-crashes between industries) is no worse than the market's.
Rows between rebalances are NaN (hold / drift) to avoid drift turnover costs.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from harness import INDUSTRIES, MarketData, Strategy
from tails import cvar, frontier_weights

WIN = 1260      # 5y of daily returns for the tail estimate (63 obs in the 5% tail)
BETA = 0.95     # CVaR level
WMAX = 0.25     # at least 4 industries
LOOK, SKIP = 252, 21  # 12-1 month momentum


class TailChiseledFrontier(Strategy):
    name = "fractal:tails_chiseled_frontier"
    refit_every = None  # nothing learned; everything is a trailing-window computation

    def _weights(self, In: np.ndarray, mn: np.ndarray, k: int) -> np.ndarray:
        X = In[k - WIN + 1:k + 1]
        p = np.prod(1.0 + In[k - LOOK + 1:k - SKIP + 1], axis=0)
        rank = np.argsort(np.argsort(p, kind="stable"), kind="stable")
        score = (rank - 5.5) / 5.5
        cap = cvar(mn[k - WIN + 1:k + 1], BETA)
        return frontier_weights(X, score, cap, BETA, WMAX)

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        cal = data.dates
        In = data.returns[INDUSTRIES].to_numpy(dtype=np.float64)
        mn = data.returns["Mkt"].to_numpy(dtype=np.float64)
        out = pd.DataFrame(np.nan, index=dates, columns=["Mkt"] + INDUSTRIES)
        pos = cal.get_indexer(dates)
        for d, k in zip(dates, pos):
            if k < WIN or cal[k - 1].month == cal[k].month:
                continue  # not the first trading day of a month: hold
            w = self._weights(In, mn, k)
            out.loc[d, INDUSTRIES] = w
            out.loc[d, "Mkt"] = 0.0
        return out
