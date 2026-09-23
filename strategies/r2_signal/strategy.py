"""r2:signal_mom_blend12 -- 49-industry momentum with a three-way 12-month signal blend.

Signal: for each industry with valid data, average its cross-sectional percentile ranks on
  * 12-0 momentum  (log return over the last 252 trading days, no skip)
  * 12-1 momentum  (days t-252 .. t-21, the classic skip-month signal)
  * 12-7 momentum  (days t-252 .. t-126, "intermediate" momentum)
Portfolio (unchanged from the round-2 baseline): hold the top third by the blended score,
equal weight, rebalanced on the first trading day of each month.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

from harness import I49, MarketData, Strategy

YEAR, MONTH, HALF = 252, 21, 126
LEGS = ((0, YEAR), (MONTH, YEAR), (HALF, YEAR))   # (skip, lookback) in trading days
TOP_FRAC = 1 / 3


class SignalMomBlend12(Strategy):
    name = "r2:signal_mom_blend12"
    refit_every = None  # nothing to learn

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.tradeable_returns()[I49]
        lp = np.log1p(R.fillna(0.0)).cumsum()
        valid = R.notna().rolling(YEAR).sum() >= YEAR - 2   # hold only industries with recent data
        cal = data.dates
        pos = cal.get_indexer(dates)
        prev_month = np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        first = dates[dates.month != prev_month]           # first trading day of each month

        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        for d in first:
            i = cal.get_loc(d)
            ok = valid.iloc[i]
            if i < YEAR or not ok.any():
                continue
            score = sum(
                (lp.iloc[i - s] - lp.iloc[i - n])[ok].rank(pct=True)
                for s, n in LEGS
            )
            k = max(1, int(round(ok.sum() * TOP_FRAC)))
            top = score.nlargest(k).index
            out.loc[d] = 0.0
            out.loc[d, top] = 1.0 / k
        return out
