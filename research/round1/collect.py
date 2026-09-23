"""Round-1 review: capture each strategy's daily dev-window returns (dev data only).

Usage: python research/round1/collect.py <strategy_dir> [<strategy_dir> ...]
Writes research/round1/equity_<dir>.csv (daily equity over the dev window).
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import pathlib
import sys

import harness.runner as runner
from harness.__main__ import load_strategy
from harness.data import load_dev

OUT = pathlib.Path(__file__).resolve().parent
captured = {}
_sim = runner.simulate


def _capture(*a, **k):
    res = _sim(*a, **k)
    captured["sim"] = res
    return res


runner.simulate = _capture

for d in sys.argv[1:]:
    strat = load_strategy(f"strategies/{d}/strategy.py")
    res = runner.run(strat, window="dev", data=load_dev(), ledger=False)
    captured["sim"].equity.to_csv(OUT / f"equity_{d}.csv")
    print(f"{d:24s} {res.cagr:+.2%}  ({res.runtime_s}s)", flush=True)
