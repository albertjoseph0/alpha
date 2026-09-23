"""Market data access for the CAGR harness.

The dataset (data/market_daily.csv, built by data/fetch_data.py from the
Kenneth R. French Data Library) holds simple daily total returns, as decimals:

    Mkt                  US total stock market (CRSP value-weighted)
    NoDur ... Other      12 value-weighted US industry portfolios
    RF                   daily risk-free rate (1-month T-bill); what cash earns

All 13 non-RF columns are tradeable. Strategies never read the CSV themselves:
the harness hands them a `MarketData` truncated at the decision date.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA_PATH = REPO / "data" / "market_daily.csv"

INDUSTRIES = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq",
              "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]
ASSETS = ["Mkt"] + INDUSTRIES  # tradeable universe (column order is canonical)

# Scoring windows. Data before a window's start is available for fitting.
DEV_END = pd.Timestamp("1999-12-31")
WINDOWS = {
    "dev": (pd.Timestamp("1950-01-01"), DEV_END),       # agents iterate here (official dev score)
    "dev_a": (pd.Timestamp("1950-01-01"), pd.Timestamp("1974-12-31")),  # dev halves, for
    "dev_b": (pd.Timestamp("1975-01-01"), DEV_END),                     # internal validation
    "holdout": (pd.Timestamp("2000-01-01"), None),      # sealed: final evaluation only
}


@dataclass(frozen=True)
class MarketData:
    """Daily returns up to (and including) the last date in the index."""
    returns: pd.DataFrame  # index: trading dates; columns: ASSETS
    rf: pd.Series          # index: trading dates

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.returns.index

    @property
    def assets(self) -> list[str]:
        return list(self.returns.columns)

    @property
    def last_date(self) -> pd.Timestamp:
        return self.returns.index[-1]

    def prices(self) -> pd.DataFrame:
        """Total-return index levels (start at 1.0 before the first return)."""
        return (1.0 + self.returns).cumprod()

    def log_returns(self) -> pd.DataFrame:
        return np.log1p(self.returns)

    def until(self, date) -> "MarketData":
        """Copy of the data up to and including `date`."""
        date = pd.Timestamp(date)
        return MarketData(self.returns.loc[:date].copy(), self.rf.loc[:date].copy())

    def tail(self, n: int) -> "MarketData":
        return MarketData(self.returns.iloc[-n:].copy(), self.rf.iloc[-n:].copy())


def load(until=None) -> MarketData:
    """Full dataset (optionally truncated). Strategies must NOT call this."""
    df = pd.read_csv(DATA_PATH, index_col="date", parse_dates=["date"])
    if until is not None:
        df = df.loc[:pd.Timestamp(until)]
    return MarketData(df[ASSETS].copy(), df["RF"].copy())


def load_dev() -> MarketData:
    """Data through the end of the dev window (1999-12-31).

    This is the ONLY data strategy developers may look at for research,
    exploratory analysis, or hyper-parameter selection. Post-1999 data is the
    sealed holdout.
    """
    return load(until=DEV_END)
