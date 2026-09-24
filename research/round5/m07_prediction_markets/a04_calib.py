"""Calibration of the leading side (win rate vs tradeable price, 95% event-bootstrap CI), DEV vs TEST, at the
frozen horizons (Polymarket H=72h, Kalshi H=1h) plus H=24h.  Descriptive; no parameters chosen here.

usage: a04_calib.py   -> out/calib_frozenH.csv, out/calib_DEV_TEST.png
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import ROOT  # noqa
import lib_fl as L  # noqa

D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
O = os.path.join(os.path.dirname(__file__), "out")
BINS = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0]
rows = []
for per in ("DEV", "TEST"):
    for v in ("poly", "kalshi"):
        s = pd.read_csv(os.path.join(D, f"snap_{v}_{per}.csv.gz"), low_memory=False)
        s["base"] = (s.disc_ok & s.on_sched) if v == "kalshi" else True
        for H in ((72, 24) if v == "poly" else (1, 24)):
            c = L.calib(s[s.base & (s.H == H) & (s.age_h <= 24)], BINS)
            c.insert(0, "H", H)
            c.insert(0, "venue", v)
            c.insert(0, "period", per)
            rows.append(c)
cc = pd.concat(rows)
cc["gap"] = cc.win - cc.mean_p
cc.to_csv(os.path.join(O, "calib_frozenH.csv"), index=False)
print(cc.round(4).to_string(index=False))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, (v, H) in zip(axes, (("poly", 72), ("kalshi", 1))):
    for per, col in (("DEV", "tab:blue"), ("TEST", "tab:orange")):
        c = cc[(cc.period == per) & (cc.venue == v) & (cc.H == H)]
        ax.errorbar(c.mean_p, c.win, yerr=[c.win - c.lo, c.hi - c.win], fmt="o-", ms=3, capsize=2, color=col, label=per)
    ax.plot([0.5, 1], [0.5, 1], "k--", lw=0.8)
    ax.axvspan(0.85 if v == "poly" else 0.95, 0.97, color="grey", alpha=0.15, label="frozen price band")
    ax.set_xlim(0.5, 1.0); ax.set_ylim(0.4, 1.02)
    ax.set_title(f"{v} H={H}h: realized win rate vs price of leading side")
    ax.set_xlabel("price at decision (Kalshi ask, Polymarket hourly price)"); ax.set_ylabel("realized win rate")
    ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(O, "calib_DEV_TEST.png"), dpi=110)
