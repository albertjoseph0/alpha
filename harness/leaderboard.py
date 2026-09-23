"""Collect strategies/*/result_*.json into a CAGR leaderboard.

    python -m harness.leaderboard            # prints markdown, writes results/leaderboard.md
"""
from __future__ import annotations

import json
import pathlib

from . import benchmarks
from .runner import run

REPO = pathlib.Path(__file__).resolve().parent.parent


def collect() -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for f in sorted(REPO.glob("strategies/*/result_*.json")):
        if f.parent.name.startswith("_"):
            continue
        r = json.loads(f.read_text())
        rows.setdefault(r["strategy"], {"dir": f.parent.name})[r["window"]] = r["cagr"]
    return rows


def render(include_holdout: bool) -> str:
    rows = collect()
    windows = (["holdout"] if include_holdout else []) + ["dev", "dev_a", "dev_b", "early"]
    bench = {}
    for cls in benchmarks.ALL:
        for w in windows:
            bench.setdefault(cls.name, {"dir": "harness/benchmarks.py"})[w] = run(cls(), window=w, ledger=False).cagr
    key = "holdout" if include_holdout else "dev"
    ordered = sorted(rows.items(), key=lambda kv: kv[1].get(key, float("-inf")), reverse=True)
    head = "| rank | strategy | " + " | ".join(f"CAGR {w}" for w in windows) + " | dir |"
    sep = "|---:|---|" + "---:|" * len(windows) + "---|"
    lines = [head, sep]
    fmt = lambda v: "—" if v is None else f"{v:+.2%}"
    for i, (name, r) in enumerate(ordered, 1):
        lines.append(f"| {i} | {name} | " + " | ".join(fmt(r.get(w)) for w in windows) + f" | {r['dir']} |")
    for name, r in bench.items():
        lines.append(f"| — | {name} | " + " | ".join(fmt(r.get(w)) for w in windows) + f" | {r['dir']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    import os
    md = render(include_holdout=os.environ.get("ALPHA_HOLDOUT") == "1")
    out = REPO / "results" / "leaderboard.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("# CAGR leaderboard\n\n" + md + "\n")
    print(md)
