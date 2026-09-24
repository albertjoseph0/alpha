"""Analysis stage 2 (DEV only): calibration curves, parameter grid, artifact checks.

usage: a02_dev.py
Outputs (research/round5/m07_prediction_markets/out/):
  calib_<venue>_DEV.csv, calib_DEV.png, grid_<venue>_DEV.csv, artifacts_DEV.txt
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import ROOT  # noqa
import lib_fl as L  # noqa

os.environ.setdefault("OMP_NUM_THREADS", "1")
D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
O = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(O, exist_ok=True)
PER = "DEV"
T0 = {"kalshi": pd.Timestamp("2021-07-15", tz="UTC").timestamp(), "poly": pd.Timestamp("2022-10-01", tz="UTC").timestamp()}
T1 = pd.Timestamp("2024-07-01", tz="UTC").timestamp()
BINS = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0]
LOS = [0.80, 0.85, 0.90, 0.93, 0.95]
HIS = [0.95, 0.97, 0.99]
log = open(os.path.join(O, f"artifacts_{PER}.txt"), "w")


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    log.write(s + "\n")


snaps = {}
k = pd.read_csv(os.path.join(D, f"snap_kalshi_{PER}.csv.gz"))
k["base"] = k.disc_ok & k.on_sched
snaps["kalshi"] = k
if os.path.exists(os.path.join(D, f"snap_poly_{PER}.csv.gz")):
    p = pd.read_csv(os.path.join(D, f"snap_poly_{PER}.csv.gz"), low_memory=False)
    # final outcomePrices must be a clean resolution (1/0) or a 50-50 void
    p["clean"] = p.result.isin(['["0", "1"]', '["1", "0"]', '["0.5", "0.5"]'])
    p["base"] = p.clean
    snaps["poly"] = p

# ------------------------------------------------------------------ artifacts
P("=== ARTIFACT CHECKS (DEV)")
P("kalshi markets", k.mkt.nunique(), "events", k.event.nunique(), "results", k.drop_duplicates("mkt").result.value_counts(dropna=False).to_dict())
m1 = k.drop_duplicates("mkt")
P("kalshi on-schedule share", round(m1.on_sched.mean(), 3), "| can_close_early share", round(m1.can_close_early.mean(), 3))
for H in (1, 24):
    x = k[(k.H == H) & k.p.notna()]
    P(f"kalshi H={H}: leading-side ask >=0.99: {np.mean(x.p >= 0.99):.3f}; in [0.85,0.97]: {np.mean(x.p.between(.85, .97)):.3f}; disc_ok share {x.disc_ok.mean():.3f}")
if "poly" in snaps:
    m2 = p.drop_duplicates("mkt")
    P("poly markets", len(m2), "events", m2.event.nunique(), "final prices:", m2.result.value_counts().head(6).to_dict())
    P("poly uma status", m2.uma.value_counts(dropna=False).to_dict())

# ------------------------------------------------------------------ calibration
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa

fig, axes = plt.subplots(1, len(snaps), figsize=(6 * len(snaps), 5), squeeze=False)
for ax, (v, s) in zip(axes[0], snaps.items()):
    rows = []
    for H in (1, 4, 24, 72):
        c = L.calib(s[s.base & (s.H == H) & (s.age_h <= 24)], BINS)
        c.insert(0, "H", H)
        rows.append(c)
        ax.errorbar(c.mean_p, c.win, yerr=[c.win - c.lo, c.hi - c.win], fmt="o-", ms=3, capsize=2, label=f"H={H}h")
    cc = pd.concat(rows)
    cc.to_csv(os.path.join(O, f"calib_{v}_{PER}.csv"), index=False)
    P(f"--- calibration {v} (win rate of leading side vs tradeable price; 95% CI event-bootstrap)")
    P(cc.round(4).to_string(index=False))
    ax.plot([0.5, 1], [0.5, 1], "k--", lw=0.8)
    ax.set_xlim(0.5, 1.0); ax.set_ylim(0.4, 1.02)
    ax.set_title(f"{v} DEV: realized vs price (ask{'' if v == 'kalshi' else '~mid'})")
    ax.set_xlabel("price of leading side at decision time"); ax.set_ylabel("realized win rate")
    ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(O, f"calib_{PER}.png"), dpi=110)

# ------------------------------------------------------------------ grid
for v, s in snaps.items():
    rows = []
    for H in sorted(s.H.unique()):
        for lo in LOS:
            for hi in HIS:
                if hi <= lo:
                    continue
                for kk in (1.0, 2.0):
                    b = L.select(s, H, lo, hi, k=kk, filters=["base"])
                    if len(b) < 20:
                        continue
                    e = L.event_bets(b)
                    sim = L.simulate(e, f=0.05, start=T0[v], end=T1)
                    ci = L.boot_ci(e.pnl.values)
                    cr = L.boot_ci(e.ret.values)
                    rows.append(dict(H=H, lo=lo, hi=hi, k=kk, events=len(e), mkts=len(b), mean_p=e.p.mean(),
                                     win=e.won.mean(), pnl_c=100 * e.pnl.mean(), pnl_lo=100 * ci[0], pnl_hi=100 * ci[1],
                                     fee_c=100 * b.fee.mean(), ret_bet=e.ret.mean(), ret_lo=cr[0], ret_hi=cr[1], hold_d=e.days.median(),
                                     deployed_ann=L.deployed_rate(e), **{"sim_" + a: b_ for a, b_ in sim.items()}))
    g = pd.DataFrame(rows)
    g.to_csv(os.path.join(O, f"grid_{v}_{PER}.csv"), index=False)
    P(f"--- grid {v} (k=1 base costs), sorted by sim CAGR (f=5%/event)")
    P(g[g.k == 1].sort_values("sim_cagr", ascending=False).head(20).round(4).to_string(index=False))
    ok = g[(g.k == 1) & (g.events >= 100)]
    if len(ok):
        best = ok.sort_values("ret_lo", ascending=False).iloc[0]
        P(f"=== SELECTED ({v}) by max lower-95% CI of mean return/$ (k=1, >=100 event-bets): "
          f"H={best.H} lo={best.lo} hi={best.hi} events={best.events} ret={best.ret_bet:.4f} CI=({best.ret_lo:.4f},{best.ret_hi:.4f})")
    P(f"--- grid {v}: fraction of k=1 cells with positive mean pnl: {(g[g.k == 1].pnl_c > 0).mean():.2f}; "
      f"with CI lower bound > 0: {(g[g.k == 1].pnl_lo > 0).mean():.2f}")

P("SPY CAGR kalshi-DEV window", round(L.spy_cagr(T0["kalshi"], T1, ROOT), 4), "poly-DEV window", round(L.spy_cagr(T0["poly"], T1, ROOT), 4))
log.close()
