"""Deterministic portfolio simulator: target weights -> equity curve -> CAGR.

Every strategy is scored by the exact same code path with the same frictions:
  * EXEC_LAG = 1: a decision made at the close of day t trades at the close
    of day t+1 and earns returns from day t+2 onward. (Prevents exploiting the
    stale-price autocorrelation in old index data, and matches reality: you
    cannot trade at the close you just observed. See research/REVIEW.md.)
  * COST = 5 bp per unit of one-way turnover, measured against drifted weights.
  * GROSS_CAP = 1: rows with sum(|w|) > 1 are scaled down to 1 (and counted).
  * Cash (1 - sum(w)) earns the daily T-bill rate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import ASSETS, MarketData

EXEC_LAG = 1
COST_PER_TURNOVER = 0.0005
GROSS_CAP = 1.0
_GROSS_TOL = 1e-9


@dataclass
class SimResult:
    equity: pd.Series          # end-of-day equity over the scoring window (starts ~1.0)
    start: pd.Timestamp        # first scored day
    end: pd.Timestamp          # last scored day
    years: float
    cagr: float
    gross_violations: int      # rows scaled down because sum(|w|) > GROSS_CAP
    ruined: bool


def cagr_from_equity(final_equity: float, years: float) -> float:
    if final_equity <= 0:
        return -1.0
    return final_equity ** (1.0 / years) - 1.0


def simulate(decisions: pd.DataFrame, data: MarketData,
             start: pd.Timestamp, end: pd.Timestamp | None) -> SimResult:
    """Score `decisions` (indexed by decision date) over [start, end].

    `decisions` must cover every decision date that feeds the window, i.e. the
    calendar dates from (first scored day - EXEC_LAG - 1) through
    (last scored day - EXEC_LAG - 1). A row of all-NaN means "hold / drift".
    """
    cal = data.dates
    k0 = int(cal.searchsorted(start, side="left"))
    kN = int(cal.searchsorted(end, side="right")) - 1 if end is not None else len(cal) - 1
    if k0 - EXEC_LAG - 1 < 0 or kN < k0:
        raise ValueError("window leaves no room for the execution lag / is empty")

    shift = EXEC_LAG + 1
    need = cal[k0 - shift: kN - shift + 1]
    tradeable = data.tradeable_returns()
    cols = list(tradeable.columns)
    dec = decisions.reindex(columns=cols)
    missing = need.difference(dec.index)
    if len(missing):
        raise ValueError(f"decisions missing {len(missing)} required dates, e.g. {missing[:3].tolist()}")
    dec = dec.loc[need]
    hold = dec.isna().all(axis=1).to_numpy()
    W = dec.fillna(0.0).to_numpy(dtype=float)

    # NaN return = asset unavailable that day; booked as 0 (no gain, no loss).
    R = np.nan_to_num(tradeable.iloc[k0:kN + 1].to_numpy(dtype=float), nan=0.0)
    RF = data.rf.iloc[k0:kN + 1].to_numpy(dtype=float)
    n, m = R.shape

    equity = np.empty(n)
    eq = 1.0
    h_drift = np.zeros(m)          # start fully in cash
    violations = 0
    ruined = False
    for i in range(n):
        if hold[i]:
            target = h_drift
        else:
            target = W[i]
            gross = np.abs(target).sum()
            if gross > GROSS_CAP + _GROSS_TOL:
                target = target * (GROSS_CAP / gross)
                violations += 1
        # Trade at the previous close (after the execution lag), pay costs.
        turnover = np.abs(target - h_drift).sum()
        eq *= 1.0 - COST_PER_TURNOVER * turnover
        # Earn today's return.
        p = float(target @ R[i] + (1.0 - target.sum()) * RF[i])
        eq *= 1.0 + p
        if eq <= 0.0 or not np.isfinite(eq):
            equity[i:] = 0.0
            ruined = True
            break
        equity[i] = eq
        h_drift = target * (1.0 + R[i]) / (1.0 + p)

    idx = cal[k0:kN + 1]
    # Period runs from the close before the first scored day to the last scored close.
    years = (idx[-1] - cal[k0 - 1]).days / 365.25
    final = 0.0 if ruined else equity[-1]
    return SimResult(
        equity=pd.Series(equity, index=idx, name="equity"),
        start=idx[0], end=idx[-1], years=years,
        cagr=cagr_from_equity(final, years),
        gross_violations=violations, ruined=ruined,
    )
