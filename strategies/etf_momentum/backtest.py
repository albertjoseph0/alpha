"""Backtest the ETF version through the same harness engine + causality audit.

Usage: python strategies/etf_momentum/backtest.py
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import json
import pathlib
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness.runner as runner
from harness import Strategy
from harness.data import WINDOWS, MarketData, load
from strategy import ETFRank5Stag4

R = pd.read_csv(HERE.parents[1] / "data" / "etf_daily.csv", index_col="date", parse_dates=["date"])
R = R.iloc[1:]  # first row is all-NaN (pct_change)
UNIVERSE = [c for c in R.columns if c != "SPY"]
rf = load().rf.reindex(R.index).ffill().fillna(0.0)   # T-bill; carried forward past French data end
DATA = MarketData(R, rf)

WINDOWS.update({
    "etf_2000": (pd.Timestamp("2000-01-01"), None),                        # thin universe early on
    "etf_2000_06": (pd.Timestamp("2000-01-01"), pd.Timestamp("2006-12-31")),
    "etf_2007": (pd.Timestamp("2007-01-01"), None),                        # full breadth (~35+ ETFs)
})


class BuyHold(Strategy):
    refit_every = None

    def __init__(self, t): self.t, self.name = t, f"buy & hold {t}"

    def predict(self, data, dates): return pd.DataFrame({self.t: 1.0}, index=dates)


class EqualWeightMonthly(Strategy):
    name = "equal-weight available ETFs, monthly"
    refit_every = None

    def predict(self, data, dates):
        Rt = data.tradeable_returns()[UNIVERSE]
        cal = data.dates
        pos = cal.get_indexer(dates)
        first = dates.month != np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        avail = Rt.notna().rolling(5).sum().reindex(dates) >= 5
        out = pd.DataFrame(np.nan, index=dates, columns=UNIVERSE)
        for d in dates[first]:
            a = avail.loc[d]
            out.loc[d] = a.astype(float) / max(a.sum(), 1)
        return out


captured = {}
_sim = runner.simulate


def _cap(*a, **k):
    res = _sim(*a, **k)
    captured["sim"] = res
    return res


runner.simulate = _cap

strats = [
    ETFRank5Stag4(UNIVERSE),
    ETFRank5Stag4(UNIVERSE, frac=1 / 3, tranche_days=(0,), rank_weight=False,
                  name="etf:plain_mom_top_third (baseline analog)"),
    BuyHold("SPY"),
    EqualWeightMonthly(),
]
results, curves = {}, {}
for w in ("etf_2000", "etf_2000_06", "etf_2007"):
    for s in strats:
        res = runner.run(s, window=w, data=DATA, ledger=False)
        results.setdefault(s.name, {})[w] = res.cagr
        if w == "etf_2000":
            curves[s.name] = captured["sim"].equity

eq = pd.DataFrame(curves)
dd = (eq / eq.cummax() - 1).min()
ret = eq.pct_change().dropna()
yr = (1 + ret).groupby(ret.index.year).prod() - 1
top = strats[0].name
print(f"{'strategy':45s} {'2000-26':>8s} {'2000-06':>8s} {'2007-26':>8s} {'maxDD':>7s}")
for n, r in results.items():
    print(f"{n:45s} {r['etf_2000']:+8.2%} {r['etf_2000_06']:+8.2%} {r['etf_2007']:+8.2%} {dd[n]:+7.1%}")
beat = int((yr[top] > yr["buy & hold SPY"]).sum())
print(f"\n{top} beat SPY in {beat} of {len(yr)} calendar years")
print((yr[[top, 'buy & hold SPY']] * 100).round(1).to_string())
(HERE / "results.json").write_text(json.dumps({"cagr": results, "max_drawdown": dd.to_dict(),
                                                 "years_beating_spy": beat, "years": len(yr)}, indent=2))
