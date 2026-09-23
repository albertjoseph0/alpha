"""ETF version of r2:construct_rank5_stag4 (the rank-1 holdout strategy), for real-world use.

Identical rule, different universe: US industry ETFs (data/etf_daily.csv, built by
data/fetch_etfs.py) instead of the 49 Fama-French industry portfolios.
  * signal: 12-1 month total-return momentum (log change t-252 -> t-21 trading days);
    eligible = >= 250 valid days in the last 252 and valid on each of the last 5 days;
  * holdings: top fifth of eligible ETFs, weights linear in rank (best = k, ..., k-th = 1);
  * four staggered tranches, refreshed on trading days 0, 5, 10, 15 of each month;
    the portfolio is their average. Always fully invested, long only.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from harness import Strategy

FRAC = 1 / 5
TRANCHE_DAYS = (0, 5, 10, 15)
LOOKBACK, SKIP = 252, 21


class ETFRank5Stag4(Strategy):
    name = "etf:construct_rank5_stag4"
    refit_every = None

    def __init__(self, universe, frac=FRAC, tranche_days=TRANCHE_DAYS, rank_weight=True, name=None):
        self.universe, self.frac, self.tranche_days, self.rank_weight = list(universe), frac, tranche_days, rank_weight
        if name:
            self.name = name

    def predict(self, data, dates):
        R = data.tradeable_returns()[self.universe]
        cal = data.dates
        vals = R.to_numpy(dtype=np.float64)
        ok = ~np.isnan(vals)
        lp = np.cumsum(np.log1p(np.where(ok, vals, 0.0)), axis=0)
        cnt = np.cumsum(ok, axis=0)

        mkey = cal.year.to_numpy() * 12 + cal.month.to_numpy()
        ms_idx = np.flatnonzero(np.r_[True, mkey[1:] != mkey[:-1]])
        last = int(cal.get_indexer([dates[-1]])[0])
        events = sorted((i + off, j) for j, off in enumerate(self.tranche_days) for i in ms_idx
                        if i >= LOOKBACK + 1 and i + off <= last)

        n = len(self.universe)
        tranche_w, targets = {}, {}
        for t, j in events:
            mom = lp[t - SKIP] - lp[t - LOOKBACK]
            valid = (cnt[t] - cnt[t - LOOKBACK] >= 250) & (cnt[t] - cnt[t - 5] >= 5)
            elig = np.flatnonzero(valid)
            if len(elig) < 5:
                continue
            k = max(1, int(round(len(elig) * self.frac)))
            order = elig[np.argsort(-mom[elig], kind="stable")][:k]
            w = np.zeros(n)
            w[order] = np.arange(k, 0, -1, dtype=np.float64) if self.rank_weight else 1.0
            tranche_w[j] = w / w.sum()
            tw = sum(tranche_w.values())
            targets[t] = tw / tw.sum()

        out = pd.DataFrame(np.nan, index=dates, columns=self.universe)
        pos = cal.get_indexer(dates)
        for r, p in enumerate(pos):
            if p in targets:
                out.iloc[r] = targets[p]
        return out
