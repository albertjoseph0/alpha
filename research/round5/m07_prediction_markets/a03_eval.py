"""Evaluate ONE frozen rule on one period (DEV or TEST) for one venue, with all report metrics.

usage: a03_eval.py PERIOD VENUE H LO HI [tag]
Writes out/eval_<venue>_<PERIOD>_<tag>.txt and out/bets_<venue>_<PERIOD>_<tag>.csv.gz
Metrics: bets/events, win rate vs price, edge per contract after fees (event-bootstrap CI), return per $,
hold time, 100%-deployed annual rate (upper bound), calendar-time portfolio CAGR at f=5%/10% of equity per
event (scale-free, sample opportunities only), capacity-capped $ portfolios (K = 10k/100k/1M, stake <= 10% of
the prior-24h traded $), max drawdown, worst losing streak, 2x costs, per-year and per-category splits,
artifact sensitivities (no tape-discovery filter, off-schedule closes, price >= 0.99 excluded...).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import ROOT  # noqa
import lib_fl as L  # noqa

D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
O = os.path.join(os.path.dirname(__file__), "out")
PER, V, H, LO, HI = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
TAG = sys.argv[6] if len(sys.argv) > 6 else "frozen"
WIN = {("DEV", "kalshi"): ("2021-07-15", "2024-07-01"), ("DEV", "poly"): ("2022-10-01", "2024-07-01"),
       ("TEST", "kalshi"): ("2024-07-01", "2026-07-20"), ("TEST", "poly"): ("2024-07-01", "2026-09-01")}
T0, T1 = [pd.Timestamp(x, tz="UTC").timestamp() for x in WIN[(PER, V)]]
out = open(os.path.join(O, f"eval_{V}_{PER}_{TAG}.txt"), "w")


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    out.write(s + "\n")


s = pd.read_csv(os.path.join(D, f"snap_{'kalshi' if V == 'kalshi' else 'poly'}_{PER}.csv.gz"), low_memory=False)
if V == "kalshi":
    s["base"] = s.disc_ok & s.on_sched
    s["cap"] = 0.10 * s.v24 * s.p                     # $ : 10% of contracts traded in the prior 24h
else:
    s["clean"] = s.result.isin(['["0", "1"]', '["1", "0"]', '["0.5", "0.5"]'])
    s["base"] = s.clean
    s["cap"] = 0.10 * s.vol_total / s.life_d          # $ : 10% of average daily $ volume (lifetime avg)
    jf = os.path.join(D, f"poly_jev_{PER}.csv.gz")
    if os.path.exists(jf):                            # Jev market-type labels (descriptive only)
        j = pd.read_csv(jf, dtype={"mkt": str})
        s["mkt"] = s.mkt.astype(str)
        s = s.merge(j, on="mkt", how="left")
        s["category"] = s.mtype.fillna("unlabeled")
        s["objective"] = s.subjective < 0.5
s["all"] = True
spy = L.spy_cagr(T0, T1, ROOT)
P(f"=== {V} {PER} rule: buy leading side at H={H}h before scheduled close if tradeable price in [{LO},{HI}]")
P(f"window {WIN[(PER, V)]}, SPY CAGR {spy:.4f}; target = SPY + 0.20 = {spy + 0.20:.4f}")


def report(b, label, full=True):
    if len(b) == 0:
        P(label, "no bets")
        return None
    e = L.event_bets(b)
    ci = L.boot_ci(e.pnl.values)
    ci_r = L.boot_ci(e.ret.values)
    r = dict(events=len(e), mkts=len(b), mean_p=e.p.mean(), win=e.won.mean(), pnl_c=100 * e.pnl.mean(),
             pnl_ci=(round(100 * ci[0], 3), round(100 * ci[1], 3)), ret=e.ret.mean(), ret_ci=(round(ci_r[0], 4), round(ci_r[1], 4)),
             fee_c=100 * b.fee.mean(), hold_d=e.days.median(), full_util_ann=L.deployed_rate(e))
    P(f"--- {label}: " + ", ".join(f"{k}={(round(v, 4) if isinstance(v, float) else v)}" for k, v in r.items()))
    if full:
        for f in (0.05, 0.10):
            sim = L.simulate(e, f=f, start=T0, end=T1)
            P(f"    sim f={f:.2f} of equity/event (sample opportunities only): " + ", ".join(f"{k}={round(v, 4)}" for k, v in sim.items()))
        for K in (1e4, 1e5, 1e6):
            sim = L.simulate(e, f=0.05, start=T0, end=T1, K=K)
            P(f"    capacity-capped sim K=${K:,.0f}: cagr={sim['cagr']:.4f} final={sim['final']:.4f} util={sim['util']:.4f}")
    return e


b1 = L.select(s, H, LO, HI, k=1.0, filters=["base"])
e1 = report(b1, "BASE costs")
b2 = L.select(s, H, LO, HI, k=2.0, filters=["base"])
report(b2, "2x COSTS")
if e1 is None:
    out.close()
    sys.exit()
b1.to_csv(os.path.join(O, f"bets_{V}_{PER}_{TAG}.csv.gz"), index=False)

yrs = (T1 - T0) / (365.25 * 86400)
P(f"--- opportunity supply: {len(e1)} event-bets over {yrs:.2f} y = {len(e1) / yrs:.0f}/yr in the sample;"
  f" median cap per event ${e1.cap.median():,.0f}, mean ${e1.cap.replace(np.inf, np.nan).mean():,.0f};"
  f" sum of caps x hold-days / period-days = ${(e1.cap * e1.days).sum() / (yrs * 365.25):,.0f} of capital deployable on average")
P(f"--- $ profit at full capacity (sum cap*ret)/yr: ${(e1.cap * e1.ret).sum() / yrs:,.0f}")
P("--- worst losing streak (consecutive losing event bets, settlement order):", L.simulate(e1)["streak"])
P("--- per year")
e1["year"] = pd.to_datetime(e1.d, unit="s").dt.year
P(e1.groupby("year").agg(n=("ret", "size"), p=("p", "mean"), win=("won", "mean"), ret=("ret", "mean"), pnl_c=("pnl", lambda x: 100 * x.mean())).round(4).to_string())
P("--- per category")
P(e1.groupby("category").agg(n=("ret", "size"), p=("p", "mean"), win=("won", "mean"), ret=("ret", "mean"), pnl_c=("pnl", lambda x: 100 * x.mean())).sort_values("n", ascending=False).head(12).round(4).to_string())
P("--- artifact sensitivities (base costs)")
if V == "kalshi":
    report(L.select(s, H, LO, HI, filters=["on_sched"]), "no tape-discovery filter (on-schedule only)", full=False)
    report(L.select(s[~s.on_sched], H, LO, HI, filters=["disc_ok"]), "OFF-schedule closes only (possible early close = lookahead)", full=False)
    report(L.select(s, H, LO, HI, filters=["all"]), "everything (no filters)", full=False)
    report(L.select(s, H, LO, HI, filters=["base"], C=1), "order size 1 contract (fee rounding)", full=False)
    report(L.select(s, H, LO, HI, filters=["base"], max_age=2), "quote age <= 2h", full=False)
else:
    report(L.select(s, H, LO, HI, filters=["all"]), "incl. unclean resolutions (0/0, 1/1 treated as reported)", full=False)
    report(L.select(s[s.vol_total >= 10000], H, LO, HI, filters=["base"]), "lifetime volume >= $10k", full=False)
    report(L.select(s, H, LO, HI, filters=["base"], max_age=2), "price age <= 2h", full=False)
    if "objective" in s:
        report(L.select(s, H, LO, HI, filters=["base", "objective"]), "Jev: objective resolution wording (p_subjective<0.5)", full=False)
        report(L.select(s[s.subjective >= 0.5], H, LO, HI, filters=["base"]), "Jev: subjective resolution wording", full=False)
b1s = b1.copy()
b1s["one_per_event"] = b1s.groupby("event").p.transform("max") == b1s.p
report(b1s[b1s.one_per_event].assign(w=1.0).drop_duplicates("event"), "one market per event (highest price)", full=False)
out.close()
