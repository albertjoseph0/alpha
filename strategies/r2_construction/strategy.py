"""r2:construct_rank5_stag4 -- 12-1 industry momentum on the 49 industries, portfolio construction only.

Signal (fixed, unchanged from the round-2 baseline): 12-1 month total-return momentum,
log price change from t-252 to t-21 trading days; an industry is eligible when it has
>= 250 valid days in the last 252 and valid data on each of the last 5 days.

Construction (the subject of this study):
  * holdings: the top fifth of eligible industries (k = round(n/5), about 10 of 49);
  * weights: linear in rank among the winners (best gets k, k-th gets 1, normalised),
    i.e. about 8 effective names, with names entering and leaving at low weight;
  * four staggered sub-portfolios (tranches), each refreshed monthly on trading day
    0, 5, 10 and 15 of the month; the portfolio is their equal-weight average. This keeps
    the signal fresh (every tranche is monthly) while removing rebalance-day timing luck;
  * always fully invested, long only, no caps, no market timing.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from harness import Strategy, I49

FRAC = 1 / 5          # fraction of eligible industries held
TRANCHE_DAYS = (0, 5, 10, 15)   # trading-day offsets of the four monthly tranches
LOOKBACK, SKIP = 252, 21


class ConstructRank5Stag4(Strategy):
    name = "r2:construct_rank5_stag4"
    refit_every = None

    def predict(self, data, dates):
        R = data.tradeable_returns()[I49]
        cal = data.dates
        vals = R.to_numpy(dtype=np.float64)
        ok = ~np.isnan(vals)
        lp = np.cumsum(np.log1p(np.where(ok, vals, 0.0)), axis=0)
        cnt = np.cumsum(ok, axis=0)

        # month starts known at each date (first trading day of each calendar month)
        mkey = cal.year.to_numpy() * 12 + cal.month.to_numpy()
        ms_idx = np.flatnonzero(np.r_[True, mkey[1:] != mkey[:-1]])
        last = int(cal.get_indexer([dates[-1]])[0])
        events = sorted((i + off, j) for j, off in enumerate(TRANCHE_DAYS) for i in ms_idx
                        if i >= LOOKBACK + 1 and i + off <= last)

        n_assets = len(I49)
        tranche_w = {}
        targets = {}
        for t, j in events:
            mom = lp[t - SKIP] - lp[t - LOOKBACK]
            valid = (cnt[t] - cnt[t - LOOKBACK] >= 250) & (cnt[t] - cnt[t - 5] >= 5)
            elig = np.flatnonzero(valid)
            if len(elig) < 5:
                continue
            k = max(1, int(round(len(elig) * FRAC)))
            order = elig[np.argsort(-mom[elig], kind="stable")][:k]
            w = np.zeros(n_assets)
            w[order] = np.arange(k, 0, -1, dtype=np.float64)
            tranche_w[j] = w / w.sum()
            tw = sum(tranche_w.values())
            targets[t] = tw / tw.sum()

        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        pos = cal.get_indexer(dates)
        for r, p in enumerate(pos):
            if p in targets:
                out.iloc[r] = targets[p]
        return out
