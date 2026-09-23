"""Walk-forward runner with a causality (look-ahead) audit. Output: CAGR.

For a scoring window the runner:
  1. Walks forward over decision dates in blocks of <= 252 trading days.
     `fit()` is called when due (every `refit_every` decision days, or once
     if None) with data ending at the block's first date.
     `predict()` is called with data ending at the block's last date.
  2. Audits causality: for sampled dates d in each block (always the first,
     plus random others) it re-calls predict(data.until(d), [d]) and requires
     the same row. Any use of data after d inside a block shows up here.
  3. Simulates the decisions with harness.engine (same frictions for all).
  4. Reports a single number: CAGR over the window.

Holdout runs require ALPHA_HOLDOUT=1 in the environment. They are reserved
for the final evaluation by the orchestrator.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .data import ASSETS, WINDOWS, MarketData, load, load_etf
from .engine import EXEC_LAG, simulate
from .strategy import Strategy

PREDICT_BLOCK = 252
AUDIT_TOL = 1e-5
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "ledger.jsonl")


class LookaheadError(AssertionError):
    """predict() output for a date changed when later data was removed."""


class HoldoutLockedError(PermissionError):
    pass


@dataclass
class RunResult:
    strategy: str
    window: str
    start: str
    end: str
    years: float
    cagr: float
    gross_violations: int
    ruined: bool
    runtime_s: float
    audited_dates: int
    git_commit: str
    timestamp: str

    def summary(self) -> str:
        return (f"{self.strategy:<42s} {self.window:<8s} {self.start} -> {self.end} "
                f"({self.years:.1f}y)   CAGR {self.cagr:+.2%}")


def _validate(block: pd.DataFrame, dates: pd.DatetimeIndex, name: str,
              cols: list[str] = ASSETS) -> pd.DataFrame:
    if not isinstance(block, pd.DataFrame):
        raise TypeError(f"{name}.predict must return a DataFrame, got {type(block)}")
    unknown = set(block.columns) - set(cols)
    if unknown:
        raise ValueError(f"{name}.predict returned non-tradeable columns: {sorted(unknown)}")
    if not block.index.equals(dates):
        raise ValueError(f"{name}.predict index must equal the requested dates")
    block = block.reindex(columns=cols).astype(float)
    vals = block.to_numpy()
    row_all_nan = np.isnan(vals).all(axis=1)
    partial_nan = np.isnan(vals).any(axis=1) & ~row_all_nan
    if partial_nan.any():
        # Missing assets inside a non-hold row mean weight 0.
        block.loc[partial_nan] = block.loc[partial_nan].fillna(0.0)
    if not np.isfinite(block.to_numpy()[~row_all_nan]).all():
        raise ValueError(f"{name}.predict returned inf values")
    return block


def _rows_equal(a: np.ndarray, b: np.ndarray) -> bool:
    if np.isnan(a).all() and np.isnan(b).all():
        return True
    a = np.nan_to_num(a, nan=0.0)
    b = np.nan_to_num(b, nan=0.0)
    return bool(np.allclose(a, b, atol=AUDIT_TOL, rtol=0.0))


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, cwd=os.path.dirname(os.path.dirname(LEDGER)), timeout=5).stdout.strip()
    except Exception:
        return ""


def run(strategy: Strategy, window: str = "dev", data: MarketData | None = None,
        audit_per_block: int = 2, seed: int = 0, ledger: bool = True,
        verbose: bool = False, long_only: bool | None = None) -> RunResult:
    if window not in WINDOWS:
        raise ValueError(f"window must be one of {sorted(WINDOWS)}")
    if window.endswith("holdout") and os.environ.get("ALPHA_HOLDOUT") != "1":
        raise HoldoutLockedError(
            f"The {window} window is sealed for the final evaluation. "
            "Develop and select on the dev windows only.")
    t0 = time.time()
    is_etf = window.startswith("etf")
    long_only = is_etf if long_only is None else long_only
    if data is None:
        data = load_etf() if is_etf else load()
    start, end = WINDOWS[window]
    cal = data.dates
    k0 = int(cal.searchsorted(start, side="left"))
    kN = int(cal.searchsorted(end, side="right")) - 1 if end is not None else len(cal) - 1
    shift = EXEC_LAG + 1
    decision_dates = cal[k0 - shift: kN - shift + 1]

    cols = list(data.tradeable_returns().columns)
    rng = np.random.default_rng(seed)
    refit = strategy.refit_every
    block_len = PREDICT_BLOCK if refit is None else max(1, min(int(refit), PREDICT_BLOCK))
    blocks, audited = [], 0
    since_fit = None
    for b0 in range(0, len(decision_dates), block_len):
        dates = decision_dates[b0: b0 + block_len]
        if since_fit is None or (refit is not None and since_fit >= refit):
            strategy.fit(data.until(dates[0]))
            since_fit = 0
        block = _validate(strategy.predict(data.until(dates[-1]), dates), dates, strategy.name, cols)
        if long_only and (block.to_numpy() < -1e-9).any():
            raise ValueError(f"{strategy.name}: negative weights are not allowed (long-only universe)")
        # Causality audit: first date of block + random others (last date has identical data).
        cands = list(range(1, len(dates) - 1))
        picks = [0] + (list(rng.choice(cands, size=min(audit_per_block - 1, len(cands)), replace=False))
                       if cands and audit_per_block > 1 else [])
        for i in picks:
            d = dates[i]
            single = _validate(strategy.predict(data.until(d), dates[i:i + 1]), dates[i:i + 1], strategy.name, cols)
            if not _rows_equal(block.iloc[i].to_numpy(), single.iloc[0].to_numpy()):
                raise LookaheadError(
                    f"{strategy.name}: weights for {d.date()} differ when data after {d.date()} is removed.\n"
                    f"  block predict : {block.iloc[i].round(6).to_dict()}\n"
                    f"  single predict: {single.iloc[0].round(6).to_dict()}")
            audited += 1
        blocks.append(block)
        since_fit += len(dates)
        if verbose:
            print(f"  decided through {dates[-1].date()}", flush=True)

    decisions = pd.concat(blocks)
    sim = simulate(decisions, data, start, end)
    res = RunResult(
        strategy=strategy.name, window=window, start=str(sim.start.date()), end=str(sim.end.date()),
        years=round(sim.years, 3), cagr=float(sim.cagr), gross_violations=sim.gross_violations,
        ruined=sim.ruined, runtime_s=round(time.time() - t0, 1), audited_dates=audited,
        git_commit=_git_commit(), timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    )
    if ledger:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        with open(LEDGER, "a") as f:
            f.write(json.dumps(asdict(res)) + "\n")
    return res
