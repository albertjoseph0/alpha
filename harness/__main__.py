"""CLI:  python -m harness <path/to/strategy.py> [--window dev|holdout] [--benchmarks]

Prints the strategy's CAGR for the window (and, with --benchmarks, the CAGR of
the reference strategies over the same window). Writes
<strategy dir>/result_<window>.json and appends to results/ledger.jsonl.

The strategy file must define either `build_strategy() -> Strategy` or exactly
one `Strategy` subclass.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import pathlib
import sys
from dataclasses import asdict

from . import benchmarks
from .runner import run
from .strategy import Strategy


def load_strategy(path: str) -> Strategy:
    p = pathlib.Path(path).resolve()
    sys.path.insert(0, str(p.parent))  # allow sibling imports inside a strategy dir
    spec = importlib.util.spec_from_file_location(f"strategy_{p.parent.name}_{p.stem}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "build_strategy"):
        return mod.build_strategy()
    classes = [c for _, c in inspect.getmembers(mod, inspect.isclass)
               if issubclass(c, Strategy) and c is not Strategy and c.__module__ == mod.__name__
               and not inspect.isabstract(c)]
    if len(classes) != 1:
        raise SystemExit(f"{path}: define build_strategy() or exactly one Strategy subclass "
                         f"(found {[c.__name__ for c in classes]})")
    return classes[0]()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m harness", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategy", nargs="?", help="path to strategy .py file")
    ap.add_argument("--window", default="dev", choices=["dev", "dev_a", "dev_b", "early", "holdout"])
    ap.add_argument("--benchmarks", action="store_true", help="also print benchmark CAGRs")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    if a.strategy:
        strat = load_strategy(a.strategy)
        res = run(strat, window=a.window, verbose=a.verbose)
        print(res.summary())
        if res.gross_violations:
            print(f"  note: {res.gross_violations} rows had sum(|w|) > 1 and were scaled down")
        out = pathlib.Path(a.strategy).resolve().parent / f"result_{a.window}.json"
        out.write_text(json.dumps(asdict(res), indent=2) + "\n")
    if a.benchmarks or not a.strategy:
        for cls in benchmarks.ALL:
            print(run(cls(), window=a.window, ledger=False).summary())


if __name__ == "__main__":
    main()
