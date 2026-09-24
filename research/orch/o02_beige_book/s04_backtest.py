"""Harness backtests of every variant at 1x and 2x the harness ETF costs.

DEV (default): uses load_etf_dev() only (data through 2015-12-31), windows etf_dev, etf_dev_a, etf_dev_b.
TEST: `ALPHA_HOLDOUT=1 python s04_backtest.py --test` (run once, after PREREG.md) on etf_holdout.
Official CAGR = harness.runner.run (with its causality audit; ledger off). Max drawdown and turnover come from
re-simulating the same decisions with harness.engine.simulate (the same code path).
Output: data/orch/o02_beige_book/backtest_<dev|test>.csv (+ equity_<dev|test>.parquet)
"""
import argparse
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import D, ETFS  # noqa: E402
from harness.data import WINDOWS, MarketData, load_etf, load_etf_dev  # noqa: E402
from harness.engine import EXEC_LAG, simulate  # noqa: E402
from harness.runner import run  # noqa: E402
from strategy import BeigeBookRotation  # noqa: E402

VARIANTS = ["ew", "mom", "dict", "lm", "jev", "mom+dict", "mom+dict+jev", "mom+jev", "dict+jev"]


class SPYHold(BeigeBookRotation):
    """Buy and hold SPY, for the same metrics table (harness benchmark gives the same CAGR)."""
    def __init__(self):
        self.name, self.variant = "o02:spy_hold", "spy"

    def predict(self, data, dates):
        return pd.DataFrame(1.0, index=dates, columns=["SPY"])   # 100% SPY every day = buy and hold


def scaled(data: MarketData, mult: float) -> MarketData:
    return MarketData(data.returns, data.rf, data.extra, data.costs * mult)


def metrics(strat, data, window):
    start, end = WINDOWS[window]
    cal = data.dates
    k0 = int(cal.searchsorted(start, side="left"))
    kN = int(cal.searchsorted(end, side="right")) - 1 if end is not None else len(cal) - 1
    shift = EXEC_LAG + 1
    dates = cal[k0 - shift: kN - shift + 1]
    dec = strat.predict(data.until(dates[-1]), dates)
    if isinstance(strat, SPYHold):
        dec = dec.reindex(columns=data.returns.columns)
    sim = simulate(dec, data, start, end)
    eq = sim.equity
    dd = float((eq / eq.cummax() - 1).min())
    W = dec.reindex(columns=ETFS).fillna(0.0)
    chg = W.diff().abs().sum(axis=1)
    n_reb = int((chg > 1e-9).sum())
    to = float(chg.sum() / 2 / sim.years)   # one-way turnover per year at rebalances (excl. drift)
    return sim, dd, n_reb, to


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        assert os.environ.get("ALPHA_HOLDOUT") == "1"
        base, windows, tag = load_etf(), ["etf_holdout"], "test"
    else:
        base, windows, tag = load_etf_dev(), ["etf_dev", "etf_dev_a", "etf_dev_b"], "dev"
    rows, eqs = [], {}
    strats = [SPYHold()] + [BeigeBookRotation(v) for v in VARIANTS]
    for mult in (1.0, 2.0):
        data = scaled(base, mult)
        for w in windows:
            for s in strats:
                res = run(s, window=w, data=data, ledger=False)
                sim, dd, n_reb, to = metrics(s, data, w)
                assert abs(sim.cagr - res.cagr) < 1e-9, (s.name, sim.cagr, res.cagr)
                rows.append({"variant": s.variant, "window": w, "cost_mult": mult, "cagr": res.cagr,
                             "max_dd": dd, "rebalances": n_reb, "turnover_yr": to, "audited": res.audited_dates})
                if mult == 1.0 and w in ("etf_dev", "etf_holdout"):
                    eqs[s.variant] = sim.equity
                print(f"{w:12s} {mult:.0f}x {s.variant:14s} CAGR {res.cagr:+.2%}  maxDD {dd:+.1%}  "
                      f"reb {n_reb:4d}  TO/yr {to:.2f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(D / f"backtest_{tag}.csv", index=False)
    pd.DataFrame(eqs).to_parquet(D / f"equity_{tag}.parquet")
    piv = df.pivot_table(index="variant", columns=["window", "cost_mult"], values="cagr")
    print((piv * 100).round(2).to_string())


if __name__ == "__main__":
    main()
