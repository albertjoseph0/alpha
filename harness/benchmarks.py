"""Reference strategies, scored by the same runner/engine as everything else."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import INDUSTRIES, MarketData
from .strategy import Strategy


class BuyHoldMarket(Strategy):
    name = "benchmark:buy_hold_market"
    refit_every = None

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.DataFrame({"Mkt": 1.0}, index=dates)


class EqualWeightIndustries(Strategy):
    """1/12 in each industry, rebalanced on the first trading day of each month."""
    name = "benchmark:equal_weight_industries_monthly"
    refit_every = None

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        cal = data.dates
        pos = cal.get_indexer(dates)
        prev_month = np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        first_of_month = dates.month != prev_month
        out = pd.DataFrame(np.nan, index=dates, columns=INDUSTRIES)
        out.loc[first_of_month, :] = 1.0 / len(INDUSTRIES)
        return out


class Cash(Strategy):
    name = "benchmark:cash_tbills"
    refit_every = None

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return pd.DataFrame({"Mkt": 0.0}, index=dates)


ALL = [BuyHoldMarket, EqualWeightIndustries, Cash]
