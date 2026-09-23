import os

import numpy as np
import pandas as pd
import pytest

from harness import ASSETS, INDUSTRIES, LookaheadError, MarketData, Strategy, run
from harness import benchmarks
from harness.data import WINDOWS, load
from harness.engine import COST_PER_TURNOVER, simulate
from harness.runner import HoldoutLockedError


def synthetic(n=12, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2001-01-01", periods=n)
    rets = pd.DataFrame(rng.normal(0, 0.01, (n, len(ASSETS))), index=idx, columns=ASSETS)
    rf = pd.Series(0.0001, index=idx)
    return MarketData(rets, rf)


# ---------- engine ----------

def test_engine_lag_cost_and_cash_by_hand():
    d = synthetic()
    cal = d.dates
    start, end = cal[4], cal[6]          # score 3 days: k = 4, 5, 6
    dec = pd.DataFrame(0.0, index=cal, columns=ASSETS)
    dec.loc[cal[2], "Mkt"] = 1.0         # decided at k=2 -> traded at close k=3 -> earns day k=4
    dec.loc[cal[3], "Mkt"] = 0.5         # -> earns day k=5
    dec.loc[cal[4], ["Mkt", "Hlth"]] = [0.25, -0.25]  # -> earns day k=6
    res = simulate(dec, d, start, end)

    r, rf, c = d.returns, d.rf, COST_PER_TURNOVER
    eq = 1.0 * (1 - c * 1.0)
    p4 = r["Mkt"].iloc[4]
    eq *= 1 + p4
    drift = (1 + r["Mkt"].iloc[4]) / (1 + p4)            # = 1.0
    eq *= 1 - c * abs(0.5 - drift)
    p5 = 0.5 * r["Mkt"].iloc[5] + 0.5 * rf.iloc[5]
    eq *= 1 + p5
    drift_mkt = 0.5 * (1 + r["Mkt"].iloc[5]) / (1 + p5)
    eq *= 1 - c * (abs(0.25 - drift_mkt) + abs(-0.25 - 0.0))
    p6 = 0.25 * r["Mkt"].iloc[6] - 0.25 * r["Hlth"].iloc[6] + (1 - 0.0) * rf.iloc[6]
    eq *= 1 + p6
    assert res.equity.iloc[-1] == pytest.approx(eq, rel=1e-12)
    years = (cal[6] - cal[3]).days / 365.25
    assert res.cagr == pytest.approx(eq ** (1 / years) - 1, rel=1e-12)


def test_engine_gross_cap_scales_and_counts():
    d = synthetic()
    cal = d.dates
    dec = pd.DataFrame(0.0, index=cal, columns=ASSETS)
    dec.loc[:, "Mkt"] = 2.0
    capped = simulate(dec, d, cal[4], cal[8])
    dec.loc[:, "Mkt"] = 1.0
    unit = simulate(dec, d, cal[4], cal[8])
    assert capped.gross_violations == 5
    assert capped.equity.iloc[-1] == pytest.approx(unit.equity.iloc[-1], rel=1e-12)


def test_engine_nan_row_means_hold():
    d = synthetic()
    cal = d.dates
    dec = pd.DataFrame(np.nan, index=cal, columns=ASSETS)
    dec.loc[cal[2], :] = 0.0
    dec.loc[cal[2], ["Mkt", "Utils"]] = 0.5
    res = simulate(dec, d, cal[4], cal[9])
    # Buy once, then drift: equity = (1-c) * (0.5*prod(1+r_Mkt) + 0.5*prod(1+r_Utils))
    g = (1 + d.returns.iloc[4:10]).prod()
    expect = (1 - COST_PER_TURNOVER) * (0.5 * g["Mkt"] + 0.5 * g["Utils"])
    assert res.equity.iloc[-1] == pytest.approx(expect, rel=1e-12)


# ---------- runner / causality audit ----------

class Peeker(Strategy):
    """Illegal: uses the next day's return (available only inside a block)."""
    name = "test:peeker"
    refit_every = None

    def predict(self, data, dates):
        nxt = data.returns["Mkt"].shift(-1).reindex(dates).fillna(0.0)
        return pd.DataFrame({"Mkt": np.sign(nxt)}, index=dates)


class Honest(Strategy):
    """Legal: sign of the trailing 20-day return."""
    name = "test:honest"
    refit_every = 63

    def predict(self, data, dates):
        mom = data.returns["Mkt"].rolling(20).sum().reindex(dates).fillna(0.0)
        return pd.DataFrame({"Mkt": np.sign(mom)}, index=dates)


def test_audit_catches_lookahead():
    with pytest.raises(LookaheadError):
        run(Peeker(), window="dev", data=load(until="1960-12-31"), ledger=False)


def test_audit_passes_causal_strategy():
    res = run(Honest(), window="dev", data=load(until="1960-12-31"), ledger=False)
    assert np.isfinite(res.cagr) and res.audited_dates > 0


def test_holdout_is_locked(monkeypatch):
    monkeypatch.delenv("ALPHA_HOLDOUT", raising=False)
    with pytest.raises(HoldoutLockedError):
        run(Honest(), window="holdout", ledger=False)


def test_fit_never_sees_the_future():
    seen = []

    class Spy(Strategy):
        name = "test:spy"
        refit_every = 252

        def fit(self, data):
            seen.append(data.last_date)

        def predict(self, data, dates):
            assert data.last_date == dates[-1]
            return pd.DataFrame({"Mkt": 1.0}, index=dates)

    data = load(until="1955-12-31")
    run(Spy(), window="dev", data=data, ledger=False)
    start = WINDOWS["dev"][0]
    assert seen[0] < start and all(a < b for a, b in zip(seen, seen[1:]))


# ---------- real-data sanity ----------

def test_buy_hold_matches_direct_compounding():
    data = load(until="1999-12-31")
    res = run(benchmarks.BuyHoldMarket(), window="dev", data=data, ledger=False)
    r = data.returns["Mkt"].loc["1950-01-01":"1999-12-31"]
    years = (r.index[-1] - data.dates[data.dates.get_loc(r.index[0]) - 1]).days / 365.25
    direct = ((1 - COST_PER_TURNOVER) * (1 + r).prod()) ** (1 / years) - 1
    assert res.cagr == pytest.approx(direct, abs=1e-12)


def test_cash_matches_tbills():
    data = load(until="1999-12-31")
    res = run(benchmarks.Cash(), window="dev", data=data, ledger=False)
    rf = data.rf.loc["1950-01-01":"1999-12-31"]
    years = (rf.index[-1] - data.dates[data.dates.get_loc(rf.index[0]) - 1]).days / 365.25
    assert res.cagr == pytest.approx((1 + rf).prod() ** (1 / years) - 1, abs=1e-12)


def test_equal_weight_benchmark_is_causal():
    res = run(benchmarks.EqualWeightIndustries(), window="dev", data=load(until="1960-12-31"),
              audit_per_block=10, ledger=False)
    assert np.isfinite(res.cagr)
