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
    "early": (pd.Timestamp("1932-01-01"), pd.Timestamp("1949-12-31")),  # pre-dev robustness check
    "holdout": (pd.Timestamp("2000-01-01"), None),      # sealed: final evaluation only
}


DATA_PATH_I49 = REPO / "data" / "market_daily_i49.csv"


def _i49_names() -> list[str]:
    if not DATA_PATH_I49.exists():
        return []
    with open(DATA_PATH_I49) as f:
        return [c for c in f.readline().strip().split(",")[1:]]


# Optional extra tradeable assets: 49 value-weighted industries ("i49_" prefix).
# NaN = portfolio did not exist that day; the engine books a 0 return for NaN,
# so strategies should only hold i49 assets with recent valid data.
I49 = _i49_names()
ALL_TRADEABLE = ASSETS + I49


@dataclass(frozen=True)
class MarketData:
    """Daily returns up to (and including) the last date in the index."""
    returns: pd.DataFrame  # index: trading dates; columns: ASSETS
    rf: pd.Series          # index: trading dates
    extra: pd.DataFrame | None = None  # 49-industry returns (columns I49), NaN = unavailable
    costs: pd.Series | None = None     # per-asset cost per unit turnover (decimal); None = engine default

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
        ex = None if self.extra is None else self.extra.loc[:date].copy()
        return MarketData(self.returns.loc[:date].copy(), self.rf.loc[:date].copy(), ex, self.costs)

    def tail(self, n: int) -> "MarketData":
        ex = None if self.extra is None else self.extra.iloc[-n:].copy()
        return MarketData(self.returns.iloc[-n:].copy(), self.rf.iloc[-n:].copy(), ex, self.costs)

    def tradeable_returns(self) -> pd.DataFrame:
        """Returns of every tradeable asset (ASSETS + I49), NaN where unavailable."""
        if self.extra is None:
            return self.returns
        return pd.concat([self.returns, self.extra], axis=1)


def load(until=None) -> MarketData:
    """Full dataset (optionally truncated). Strategies must NOT call this."""
    df = pd.read_csv(DATA_PATH, index_col="date", parse_dates=["date"])
    ex = None
    if DATA_PATH_I49.exists():
        ex = pd.read_csv(DATA_PATH_I49, index_col="date", parse_dates=["date"]).reindex(df.index)
    if until is not None:
        df = df.loc[:pd.Timestamp(until)]
        ex = None if ex is None else ex.loc[:pd.Timestamp(until)]
    return MarketData(df[ASSETS].copy(), df["RF"].copy(), None if ex is None else ex.copy())


def load_dev() -> MarketData:
    """Data through the end of the dev window (1999-12-31).

    This is the ONLY data strategy developers may look at for research,
    exploratory analysis, or hyper-parameter selection. Post-1999 data is the
    sealed holdout.
    """
    return load(until=DEV_END)


# ---------------------------------------------------------------------------
# Round 3: tradeable ETF universe (data/fetch_etf_universe.py). Long only.
# ---------------------------------------------------------------------------
ETF_PATH = REPO / "data" / "etf_universe_daily.csv"
ETF_META_PATH = REPO / "data" / "etf_universe_meta.csv"
ETF_DEV_END = pd.Timestamp("2015-12-31")
WINDOWS.update({
    "etf_dev": (pd.Timestamp("2000-01-01"), ETF_DEV_END),       # official ETF development score
    "etf_dev_a": (pd.Timestamp("2000-01-01"), pd.Timestamp("2007-12-31")),
    "etf_dev_b": (pd.Timestamp("2008-01-01"), ETF_DEV_END),
    "etf_holdout": (pd.Timestamp("2016-01-01"), None),          # sealed
})


def etf_meta() -> pd.DataFrame:
    return pd.read_csv(ETF_META_PATH).set_index("ticker")


def load_etf(until=None) -> MarketData:
    """ETF universe: returns (NaN before inception), T-bill RF, per-ETF trading costs."""
    r = pd.read_csv(ETF_PATH, index_col="date", parse_dates=["date"])
    rf = load().rf.reindex(r.index).ffill().fillna(0.0)  # French T-bill, carried past its last date
    costs = etf_meta()["cost_bps"].reindex(r.columns) / 1e4
    if until is not None:
        r, rf = r.loc[:pd.Timestamp(until)], rf.loc[:pd.Timestamp(until)]
    return MarketData(r.copy(), rf.copy(), None, costs)


def load_etf_dev() -> MarketData:
    """ETF data through 2015-12-31: the only ETF data strategy developers may look at."""
    return load_etf(until=ETF_DEV_END)
