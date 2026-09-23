"""Fast walk-forward evaluation on the dev window (same fit dates, lag, costs as the harness).

Precomputes features once, fits the ensemble at the harness's refit dates with data up to
that date, and scores with harness.engine.simulate. Appends one line per run to runs.jsonl.

  OMP_NUM_THREADS=1 .venv/bin/python strategies/transformer_allocator/research/wf.py \
      --label base [--model linear] [--baseline ew|invvol] [--set key=value ...]
"""
import argparse
import json
import os
import pathlib
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent.parent))

import numpy as np
import pandas as pd

import ta_core as T
from harness import ASSETS, WINDOWS, load_dev
from harness.engine import simulate

DEFAULT = dict(model="transformer", d=16, heads=2, layers=1, ff=32, drop=0.1, lr=2e-3,
               wd=0.1, epochs=30, patience=6, chunk=26, chunks_per_batch=16, members=4,
               purge=2, refit=756, week_sign=1)


def sub_cagr(eq, a, b):
    e = eq.loc[a:b]
    prev = eq.loc[:a].iloc[:-1]
    e0 = prev.iloc[-1] if len(prev) else 1.0
    yrs = (e.index[-1] - (prev.index[-1] if len(prev) else e.index[0])).days / 365.25
    return (e.iloc[-1] / e0) ** (1 / yrs) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    cfg = dict(DEFAULT)
    if a.model:
        cfg["model"] = a.model
    for kv in a.set:
        k, v = kv.split("=")
        cfg[k] = type(DEFAULT[k])(v) if k in DEFAULT and not isinstance(DEFAULT[k], str) else v
    t0 = time.time()
    data = load_dev()
    dates = data.dates
    R, rf = data.returns[ASSETS].to_numpy(), data.rf.to_numpy()
    F = T.features(R, week_sign=bool(cfg["week_sign"]))
    reb = T.rebalance_mask(dates)
    start, end = WINDOWS["dev"]
    k0 = int(dates.searchsorted(start)); kN = int(dates.searchsorted(end, side="right")) - 1
    dec = dates[k0 - 2: kN - 1]
    pos0 = k0 - 2
    W = np.full((len(dec), 13), np.nan)
    refit = cfg["refit"]; blk = min(refit, 252)
    since, models, fitlog = None, None, []
    for b0 in range(0, len(dec), blk):
        rows = np.arange(pos0 + b0, pos0 + min(b0 + blk, len(dec)))
        if a.baseline is None and (since is None or since >= refit):
            last = pos0 + b0
            models, info = T.fit_ensemble(F, R, rf, reb, last, cfg, int(dates[last].strftime("%Y%m%d")))
            fitlog.append({"date": str(dates[last].date()), "best_ep": [i["best_ep"] for i in info]})
            print(fitlog[-1], round(time.time() - t0), flush=True)
            since = 0
        r = rows[reb[rows]]
        if a.baseline == "ew":
            w = np.full((len(r), 13), 1 / 13)
        elif a.baseline == "invvol":
            iv = 1 / np.exp(F[r, :, 0, 2])
            w = iv / iv.sum(1, keepdims=True)
        else:
            w = T.ensemble_weights(models, F[r])[:, :13]
        W[r - pos0] = w
        since = (since or 0) + len(rows)
    dfw = pd.DataFrame(W, index=dec, columns=ASSETS)
    sim = simulate(dfw, data, start, end)
    wd = dfw.dropna()
    res = dict(label=a.label, cfg=cfg if a.baseline is None else {"baseline": a.baseline},
               dev=round(sim.cagr, 4),
               a=round(sub_cagr(sim.equity, "1950", "1974"), 4),
               b=round(sub_cagr(sim.equity, "1975", "1999"), 4),
               avg_cash=round(1 - wd.sum(1).mean(), 4), min_invested=round(wd.sum(1).min(), 3),
               avg_mkt=round(wd["Mkt"].mean(), 3), avg_hhi=round((wd ** 2).sum(1).mean(), 3),
               mean_w=wd.mean().round(3).to_dict(),
               runtime=round(time.time() - t0), fits=fitlog)
    print(json.dumps({k: v for k, v in res.items() if k != "fits"}))
    with open(HERE / "runs.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")
    dfw.to_pickle(HERE / f"w_{a.label}.pkl")


if __name__ == "__main__":
    main()
