"""Full evaluation of one frozen configuration over one period.

usage: python evaluate.py dev|test
Writes eval_<period>.json, yearly_<period>.csv, sens_<period>.csv, daily_<period>.csv.gz
"""
import json
import sys

import numpy as np
import pandas as pd

import model as M

PERIODS = {"dev": ("1990-01-01", "2007-12-31"), "test": ("2008-01-01", "2026-12-31")}
FROZEN = dict(X=0.30, m=1.00, R=12, T0=1.0, cost=0.02)  # chosen on DEV (max base CAGR), see PREREG.md

period = sys.argv[1]
START, END = PERIODS[period]
PRIMARY_MODE = "model" if period == "dev" else "actual"

df = M.load_data()
b = M.benchmarks(df, START, END)
rf = b.rf


def run(pricer=None, cost=FROZEN["cost"], **kw):
    cfg = {**FROZEN, "cost": cost, **kw}
    res, tr = M.backtest(df, START, END, X=cfg["X"], m=cfg["m"], R=cfg["R"], T0=cfg["T0"], cost=cfg["cost"],
                         pricer=pricer or M.Pricer(PRIMARY_MODE), binary=cfg.get("binary", False))
    return res, tr


res, tr = run()
r = res.ret


def monthly(x):
    return (1 + x).resample("ME").prod() - 1


def ols(y, X):
    X = np.c_[np.ones(len(X)), X]
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    return coef


def ex_best(yr, k):
    s = yr.sort_values(ascending=False).iloc[k:]
    return (1 + s).prod() ** (1 / len(s)) - 1


out = {"period": period, "start": str(r.index[0].date()), "end": str(r.index[-1].date()), "config": FROZEN,
       "pricing_mode": PRIMARY_MODE}
out["strategy"] = M.stats(r, rf)
out["spy"] = M.stats(b.spy, rf)
out["trend_spy"] = M.stats(b.trend_spy, rf)
out["n_trades"] = int(len(tr))
out["n_scheduled_rolls"] = int(res.index.to_period("Y").nunique())
out["n_regime_changes"] = int((df["up"].shift(1).loc[START:END].diff().fillna(0) != 0).sum())
out["avg_option_weight"] = float(res.optw.mean())
out["max_option_weight"] = float(res.optw.max())
out["cost_drag_per_yr"] = float((res.cost / res.nav).mean() * 252)

# betas
out["beta_daily_vs_spy"] = float(M.beta(r, b.spy))
rm, sm, tm, rfm = monthly(r), monthly(b.spy), monthly(b.trend_spy), monthly(rf)
c = ols((rm - rfm).values, (sm - rfm).values)
out["beta_monthly_vs_spy"], out["alpha_monthly_vs_spy_ann"] = float(c[1]), float(c[0] * 12)
c2 = ols((rm - rfm).values, (tm - rfm).values)
out["beta_monthly_vs_trend_spy"], out["alpha_monthly_vs_trend_spy_ann"] = float(c2[1]), float(c2[0] * 12)

# beta-matched benchmarks (hypothetical leverage financed at T-bill rate; not tradeable under the rules
# when beta > 1, used only to separate leverage from alpha)
bm = out["beta_monthly_vs_spy"]
bmt = out["beta_monthly_vs_trend_spy"]
bench_bm = bm * b.spy + (1 - bm) * rf
bench_bmt = bmt * b.trend_spy + (1 - bmt) * rf
out["beta_matched_spy"] = M.stats(bench_bm, rf)
out["beta_matched_trend_spy"] = M.stats(bench_bmt, rf)
# vol-matched trend SPY
vm = out["strategy"]["vol"] / out["trend_spy"]["vol"]
out["vol_matched_trend_spy_L"] = float(vm)
out["vol_matched_trend_spy"] = M.stats(vm * b.trend_spy + (1 - vm) * rf, rf)

# yearly + lucky-year dependence
yr = pd.DataFrame({"strategy": M.yearly(r), "spy": M.yearly(b.spy), "trend_spy": M.yearly(b.trend_spy),
                   "beta_matched_spy": M.yearly(bench_bm), "beta_matched_trend_spy": M.yearly(bench_bmt),
                   "avg_opt_weight": res.optw.groupby(res.index.year).mean()})
yr.to_csv(f"yearly_{period}.csv", float_format="%.4f")
out["years_beat_spy"] = f"{int((yr.strategy > yr.spy).sum())}/{len(yr)}"
for k in (1, 2):
    out[f"cagr_ex_best{k}_strategy"] = float(ex_best(yr.strategy, k))
    out[f"cagr_ex_best{k}_spy"] = float(ex_best(yr.spy, k))

# paired stationary block bootstrap of monthly returns: P(strategy CAGR > benchmark CAGR)
rng = np.random.default_rng(0)
M_ = np.c_[rm.values, sm.values, bench_bmt.pipe(monthly).values]
n = len(M_)
wins_spy = wins_bmt = wins20 = 0
B = 2000
for _ in range(B):
    idx = []
    while len(idx) < n:
        s0 = rng.integers(n)
        L = rng.geometric(1 / 6)
        idx.extend(((s0 + np.arange(L)) % n).tolist())
    g = np.log1p(M_[idx[:n]]).sum(0)
    wins_spy += g[0] > g[1]
    wins_bmt += g[0] > g[2]
    wins20 += (np.exp(g[0] * 12 / n) - np.exp(g[1] * 12 / n)) >= 0.20
out["p_boot_beat_spy"] = wins_spy / B
out["p_boot_beat_beta_matched_trend"] = wins_bmt / B
out["p_boot_beat_spy_by_20pts"] = wins20 / B

# sensitivities
sens = []
for lab, kw in [("primary", {}),
                ("2x cost (4%/side)", dict(cost=0.04)),
                ("vol +2", dict(pricer=M.Pricer(PRIMARY_MODE, vol_bump=0.02))),
                ("vol +4", dict(pricer=M.Pricer(PRIMARY_MODE, vol_bump=0.04))),
                ("vol +4 & 2x cost", dict(pricer=M.Pricer(PRIMARY_MODE, vol_bump=0.04), cost=0.04)),
                ("skew slope x0.5", dict(pricer=M.Pricer(PRIMARY_MODE, slope_mult=0.5))),
                ("skew slope x1.5", dict(pricer=M.Pricer(PRIMARY_MODE, slope_mult=1.5))),
                ("no box-rate spread", dict(pricer=M.Pricer(PRIMARY_MODE, box_spread=0.0))),
                ("OPTIMISTIC: ATM = var-swap - 3 vol", dict(pricer=M.Pricer(PRIMARY_MODE, atm_gap=0.03))),
                ("OPTIMISTIC: gap 3, 1%/side, no box", dict(pricer=M.Pricer(PRIMARY_MODE, atm_gap=0.03, box_spread=0.0), cost=0.01)),
                ("alt term structure: " + ("model" if PRIMARY_MODE == "actual" else "actual"),
                 dict(pricer=M.Pricer("model" if PRIMARY_MODE == "actual" else "actual"))),
                ("diagnostic: binary switch (up>=0.5)", dict(binary=True)),
                ("diagnostic: always on (no trend)", "always")]:
    if kw == "always":
        d2 = df.copy()
        d2["up"] = 1.0
        rr, t2 = M.backtest(d2, START, END, X=FROZEN["X"], m=FROZEN["m"], R=FROZEN["R"], cost=FROZEN["cost"],
                            pricer=M.Pricer(PRIMARY_MODE))
    else:
        rr, t2 = run(**kw)
    s = M.stats(rr.ret, rf)
    sens.append(dict(variant=lab, cagr=s["cagr"], vs_spy=s["cagr"] - out["spy"]["cagr"], vol=s["vol"],
                     sharpe=s["sharpe"], maxdd=s["maxdd"], trades=len(t2)))
sens = pd.DataFrame(sens)
sens.to_csv(f"sens_{period}.csv", index=False, float_format="%.4f")
out["cagr_2x_cost"] = float(sens.loc[sens.variant.str.startswith("2x"), "cagr"].iloc[0])

pd.DataFrame({"strategy": r, "spy": b.spy, "trend_spy": b.trend_spy, "rf": rf, "optw": res.optw,
              "up_lag": df["up"].shift(1).loc[START:END]}).to_csv(f"daily_{period}.csv.gz", float_format="%.6g")
tr.to_csv(f"trades_{period}.csv", index=False, float_format="%.6g")


def conv(o):
    if isinstance(o, dict):
        return {k: conv(v) for k, v in o.items()}
    if isinstance(o, (np.floating, np.integer)):
        return float(o)
    return o


json.dump(conv(out), open(f"eval_{period}.json", "w"), indent=1)
print(json.dumps(conv(out), indent=1))
print(sens.round(4).to_string())
print(yr.round(3).to_string())
