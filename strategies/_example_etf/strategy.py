"""Template for the round-3 ETF universe: 12-1 momentum across all ETFs, top 5, equal weight, monthly.

Run:   .venv/bin/python -m harness strategies/_example_etf/strategy.py --window etf_dev --benchmarks
Live:  .venv/bin/python -m harness.live strategies/_example_etf/strategy.py --capital 100000
"""
import numpy as np
import pandas as pd

from harness import MarketData, Strategy


class ETFMomentumTemplate(Strategy):
    name = "example:etf_mom_top5"
    refit_every = None

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.returns
        lp = np.log1p(R.fillna(0.0)).cumsum()
        mom = lp.shift(21) - lp.shift(252)
        eligible = R.notna().rolling(252).sum() >= 250
        cal = data.dates
        pos = cal.get_indexer(dates)
        month_start = dates.month != np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        out = pd.DataFrame(np.nan, index=dates, columns=R.columns)
        for d in dates[month_start]:
            m = mom.loc[d].where(eligible.loc[d]).dropna()
            if len(m) < 5:
                continue
            out.loc[d] = 0.0
            out.loc[d, m.nlargest(5).index] = 0.2
        return out
