"""Deep-dive lab (orchestrator, no subagents). Dev data only: ETF data ends 2015-12-31.

Provides fast evaluation of strategies on etf_dev windows and daily return capture.
Every evaluated configuration is appended to research/deep/evals.log.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "strategies" / "r3_options"))
import harness.runner as runner
from harness import benchmarks
from harness.data import load_etf_dev

LOG = pathlib.Path(__file__).resolve().parent / "evals.log"
DATA = load_etf_dev()
_cap = {}
_sim = runner.simulate


def _capture(*a, **k):
    r = _sim(*a, **k)
    _cap["sim"] = r
    return r


runner.simulate = _capture


def evaluate(strategy, windows=("etf_dev_a", "etf_dev_b", "etf_dev"), data=None, log=True, tag=""):
    out, eq = {}, None
    for w in windows:
        r = runner.run(strategy, window=w, data=data or DATA, ledger=False)
        out[w] = round(r.cagr * 100, 2)
        if w == "etf_dev":
            eq = _cap["sim"].equity
    if log:
        with open(LOG, "a") as f:
            f.write(json.dumps({"config": strategy.name, "tag": tag, **out}) + "\n")
    return out, eq


def spy_equity(window="etf_dev"):
    runner.run(benchmarks.BuyHoldSPY(), window=window, data=DATA, ledger=False)
    return _cap["sim"].equity


# ---- long-history proxy (1962-1999): independent validation, never used for ETF holdout ----
from harness.data import WINDOWS, MarketData, load as _load_fr

_P = pd.read_csv(ROOT / "data" / "proxy_long.csv", index_col="date", parse_dates=["date"])
PROXY = MarketData(_P, _load_fr(until="1999-12-31").rf.reindex(_P.index).fillna(0.0))
WINDOWS.update({
    "proxy": (pd.Timestamp("1965-01-01"), pd.Timestamp("1999-12-31")),
    "proxy_a": (pd.Timestamp("1965-01-01"), pd.Timestamp("1981-12-31")),   # rising rates
    "proxy_b": (pd.Timestamp("1982-01-01"), pd.Timestamp("1999-12-31")),   # falling rates
})


def evaluate_all(strategy, tag=""):
    """ETF dev halves + proxy halves; logs everything."""
    e, eq = evaluate(strategy, log=False)
    p, _ = evaluate(strategy, windows=("proxy_a", "proxy_b", "proxy"), data=PROXY, log=False)
    res = {**e, **p}
    with open(LOG, "a") as f:
        f.write(json.dumps({"config": strategy.name, "tag": tag, **res}) + "\n")
    return res, eq


BENCH = {}
for w in ("etf_dev_a", "etf_dev_b", "etf_dev"):
    BENCH[w] = round(runner.run(benchmarks.BuyHoldSPY(), window=w, data=DATA, ledger=False).cagr * 100, 2)
for w in ("proxy_a", "proxy_b", "proxy"):
    BENCH[w] = round(runner.run(benchmarks.BuyHoldSPY(), window=w, data=PROXY, ledger=False).cagr * 100, 2)


def verdict(res):
    return {w: round(res[w] - BENCH[w], 2) for w in BENCH}


# ---- fast grid: compute sleeve decisions once, recombine, simulate (components are audited) ----
from harness.engine import EXEC_LAG, simulate as _simulate


def decision_dates(data, window):
    s, e = WINDOWS[window]
    cal = data.dates
    k0 = int(cal.searchsorted(s)); kN = int(cal.searchsorted(e, side="right")) - 1 if e is not None else len(cal) - 1
    return cal[k0 - EXEC_LAG - 1: kN - EXEC_LAG]


def sleeve_weights(sleeve, data, span=("etf_dev",)):
    dates = decision_dates(data, span)
    return sleeve.predict(data, dates)


def trend_up(data, asset, length, dates):
    lp = np.log1p(data.returns[asset].fillna(0.0)).cumsum()
    return ((lp - lp.shift(length)) > 0).reindex(dates).astype(float)


def cagr_of(decisions, data, window):
    s, e = WINDOWS[window]
    return round(_simulate(decisions, data, s, e).cagr * 100, 2)


def regime(data, dates, lengths):
    return sum(trend_up(data, "SPY", L, dates) for L in lengths) / len(lengths)


def asset_gate(data, dates):
    """1 if an asset's excess return over T-bills, averaged over 1, 3 and 12 months, is > 0."""
    lp = np.log1p(data.returns.fillna(0.0)).cumsum()
    lrf = np.log1p(data.rf).cumsum()
    ex = sum((lp - lp.shift(n)).sub(lrf - lrf.shift(n), axis=0) for n in (21, 63, 252)) / 3
    return (ex > 0).astype(float).reindex(dates)


def combine(wo, wd, up, gate=None):
    """offense weight up (fraction), defense 1-up; gated offense picks hand their weight to defense."""
    if gate is None:
        return wo.mul(up, axis=0) + wd.mul(1 - up, axis=0)
    kept = wo * gate
    freed = (wo - kept).sum(axis=1)
    out = kept.mul(up, axis=0) + wd.mul((1 - up) + freed * up, axis=0)
    out[wo.isna().all(axis=1)] = np.nan     # keep 'hold' rows
    return out


def daily_returns(dec, data, window):
    s, e = WINDOWS[window]
    eq = _simulate(dec, data, s, e).equity
    return eq.pct_change().fillna(eq.iloc[0] - 1)


def bootstrap_p(r_strat, r_bench, block=63, n=4000, seed=0):
    """P(strategy CAGR > benchmark CAGR) under a paired circular block bootstrap."""
    rng = np.random.default_rng(seed)
    a, b = np.log1p(r_strat.to_numpy()), np.log1p(r_bench.to_numpy())
    T = len(a); nb = int(np.ceil(T / block)); wins = 0
    for _ in range(n):
        st = rng.integers(0, T, nb)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:T] % T
        wins += a[idx].sum() > b[idx].sum()
    return wins / n


def vol_cap(data, dates, target):
    lr = np.log1p(data.returns)
    v = lr.rolling(63, min_periods=60).std() * np.sqrt(252)
    return (target / v.clip(lower=1e-4)).clip(upper=1.0).reindex(dates)
