"""The one interface every strategy implements.

Timeline (enforced by the harness, not by the strategy):

    close of day t     predict() returns target weights using data <= t
    close of day t+1   the trade executes (EXEC_LAG = 1 day), 5 bp per unit turnover
    day t+2            first daily return earned by the new position

Weights are fractions of current equity per tradeable asset (see
`harness.data.ASSETS`). Rules:
  * sum(|w|) <= 1  (no leverage; shorts allowed). Larger rows are scaled down.
  * The remainder 1 - sum(w) sits in cash and earns the T-bill rate.
  * A row that is entirely NaN means "no trade today": positions drift with prices.
  * Missing asset columns are treated as weight 0.

Contract (checked by the causality audit):
  * predict(data, dates) must give, for each date d in `dates`, exactly the
    same row it would give if called as predict(data.until(d), [d]).
    In other words: the weight for d uses only data <= d.
  * predict() must not mutate model state; do all learning in fit().
  * Be deterministic: seed any randomness (e.g. from the fit date).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from .data import MarketData


class Strategy(ABC):
    #: Human-readable identifier (used in results / leaderboard).
    name: str = "unnamed"

    #: Refit cadence in trading days (decision days). None => fit once, at the
    #: start of the scoring window, on all data available at that point.
    refit_every: int | None = 252

    def fit(self, data: MarketData) -> None:
        """Learn from history. `data` ends at the refit date (inclusive)."""

    @abstractmethod
    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Target weights, index == dates, columns ⊆ ASSETS.

        `data` ends at dates[-1]. Row d may use only data up to d.
        """
