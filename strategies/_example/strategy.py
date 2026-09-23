"""Template strategy: long the market when its 200-day trend is up, else T-bills.

Run:  .venv/bin/python -m harness strategies/_example/strategy.py --benchmarks
"""
import numpy as np
import pandas as pd

from harness import MarketData, Strategy


class TrendTemplate(Strategy):
    name = "example:trend200"
    refit_every = None  # nothing to learn

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        px = data.prices()["Mkt"]
        trend = np.log(px).diff(200)              # uses only data <= each date
        w = (trend.reindex(dates) > 0).astype(float)
        return pd.DataFrame({"Mkt": w}, index=dates)
