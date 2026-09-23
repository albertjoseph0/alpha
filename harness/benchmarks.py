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


# ---------------------------------------------------------------------------
# Round 3 ETF-universe benchmarks (use with the etf_* windows).
# ---------------------------------------------------------------------------
def _month_starts(data: MarketData, dates: pd.DatetimeIndex) -> np.ndarray:
    cal = data.dates
    pos = cal.get_indexer(dates)
    return dates.month != np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)


def _available(data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
    return data.returns.notna().rolling(5).sum().reindex(dates) >= 5


class BuyHoldSPY(Strategy):
    name = "benchmark:buy_hold_SPY"
    refit_every = None

    def predict(self, data, dates):
        return pd.DataFrame({"SPY": 1.0}, index=dates)


class SixtyForty(Strategy):
    """60% SPY / 40% IEF, rebalanced monthly (the 40% sits in T-bills before IEF exists, mid-2002)."""
    name = "benchmark:60_40_SPY_IEF"
    refit_every = None

    def predict(self, data, dates):
        out = pd.DataFrame(np.nan, index=dates, columns=["SPY", "IEF"])
        ms = _month_starts(data, dates)
        ief = _available(data, dates)["IEF"].to_numpy()
        out.loc[ms, "SPY"] = 0.6
        out.loc[ms, "IEF"] = np.where(ief[ms], 0.4, 0.0)
        return out


class EqualWeightETFs(Strategy):
    name = "benchmark:equal_weight_all_etfs_monthly"
    refit_every = None

    def predict(self, data, dates):
        out = pd.DataFrame(np.nan, index=dates, columns=data.returns.columns)
        ms = _month_starts(data, dates)
        av = _available(data, dates)
        for d in dates[ms]:
            a = av.loc[d]
            out.loc[d] = a.astype(float) / max(int(a.sum()), 1)
        return out


ETF_ALL = [BuyHoldSPY, SixtyForty, EqualWeightETFs]
