"""r2:crashguard_plain49 -- 12-1 industry momentum on the 49 Fama-French industries, no crash guard.

Round-2 "crash-robust momentum" angle. Research (research/*.py, README.md) found that the
long-only, broad (top-third, equal-weight) 49-industry momentum portfolio is already crash-robust
on development data: its beta is ~1 in bear-market states and it earns positive excess returns
even in the top-decile market-rebound months. Every guard tested (Daniel-Moskowitz panic blend,
dual/absolute momentum, residual momentum, beta floor, tracking-error scaling, panic high-beta
tilt) cost CAGR or only added noise, so none is applied.

Rule: on the first trading day of each month, rank industries with >= 250 valid days in the last
252 by their log return from t-252 to t-21 trading days, and hold the top third, equal weight,
fully invested. Parameters are the textbook 12-1 lookback and top-third breadth, set a priori.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

from harness import I49, Strategy

LOOKBACK = 252   # ~12 months
SKIP = 21        # skip the most recent ~1 month
FRAC = 1 / 3     # hold the top third


class CrashGuardPlain49(Strategy):
    name = "r2:crashguard_plain49"
    refit_every = None

    def fit(self, data) -> None:
        pass

    def predict(self, data, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.tradeable_returns()[I49]
        lp = np.log1p(R.fillna(0.0)).cumsum()
        mom = lp.shift(SKIP) - lp.shift(LOOKBACK)
        valid = R.notna().rolling(LOOKBACK).sum() >= LOOKBACK - 2
        cal = data.dates
        pos = cal.get_indexer(dates)
        prev_month = np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        first = dates.month != prev_month
        out = pd.DataFrame(np.nan, index=dates, columns=I49)   # NaN row = hold / drift
        for d in dates[first]:
            m = mom.loc[d].where(valid.loc[d]).dropna()
            if m.empty:
                continue
            k = max(1, int(round(len(m) * FRAC)))
            top = m.nlargest(k).index
            out.loc[d] = 0.0
            out.loc[d, top] = 1.0 / k
        return out
