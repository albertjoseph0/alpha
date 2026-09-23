"""Today's target portfolio from a strategy, using the same code path as the backtest.

    python -m harness.live strategies/<dir>/strategy.py --capital 100000 [--refresh]

--refresh re-downloads the ETF universe first (data/fetch_etf_universe.py).
Prints the current target weights (the most recent rebalance the strategy has made)
and whole-share counts at the latest close. Place the trades yourself or via a broker.
Not financial advice.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import numpy as np
import pandas as pd

from .__main__ import load_strategy
from .data import REPO, load_etf


def target_weights(strategy, lookback_days: int = 80) -> tuple[pd.Timestamp, pd.Series]:
    data = load_etf()
    strategy.fit(data)
    dates = data.dates[-lookback_days:]
    w = strategy.predict(data, dates)
    rows = w.dropna(how="all")
    if rows.empty:
        raise SystemExit("strategy produced no target in the last few months")
    last = rows.index[-1]
    return last, rows.loc[last].fillna(0.0)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m harness.live")
    ap.add_argument("strategy")
    ap.add_argument("--capital", type=float, default=100_000.0)
    ap.add_argument("--refresh", action="store_true", help="re-download ETF prices first")
    a = ap.parse_args(argv)
    if a.refresh:
        subprocess.run([sys.executable, str(REPO / "data" / "fetch_etf_universe.py")], check=True)

    strat = load_strategy(a.strategy)
    set_on, w = target_weights(strat)
    w = w[w > 1e-6].sort_values(ascending=False)
    import yfinance as yf  # latest unadjusted close for share counts
    px = yf.download(list(w.index), period="5d", auto_adjust=False, progress=False)["Close"].iloc[-1]
    px = px if isinstance(px, pd.Series) else pd.Series({w.index[0]: float(px)})
    shares = np.floor(a.capital * w / px.reindex(w.index)).astype(int)
    print(f"{strat.name}: target set on {set_on.date()} (latest data {load_etf().last_date.date()})")
    print(f"{'ticker':8s}{'weight':>8s}{'price':>10s}{'shares':>8s}")
    for t in w.index:
        print(f"{t:8s}{w[t]:8.1%}{px[t]:10.2f}{shares[t]:8d}")
    print(f"cash (T-bills): {1 - w.sum():.1%}")


if __name__ == "__main__":
    main()
