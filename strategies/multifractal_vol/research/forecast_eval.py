"""Walk-forward comparison of volatility forecasters (dev data only).

Target: realized variance over t+2..t+22 (what a position decided at t is
exposed to). Annual refits from 1950 using all data before the refit date.
Metrics over 1950-99 and the halves: QLIKE (lower is better) and the R^2 of a
Mincer-Zarnowitz regression of log RV on log forecast.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import time
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/alpha")
sys.path.insert(0, "/home/user/alpha/strategies/multifractal_vol")
from harness import load_dev
import mfvol as mv

ASSET = sys.argv[1] if len(sys.argv) > 1 else "Mkt"
DO_MSM = "--msm" in sys.argv
H = 21

d = load_dev()
dates = d.dates
lr = np.log1p(d.returns[ASSET].to_numpy())
n = len(lr)
target = mv.fwd_rv(lr, H)

years = range(1950, 2000)
refit_idx = [int(dates.searchsorted(pd.Timestamp(f"{y}-01-01"))) for y in years] + [n]

fc = {k: np.full(n, np.nan) for k in
      ["ewma", "rv21", "garch", "gjr", "har", "mrw", "mrw_free", "mtarch", "mtarch_nolev", "msm"]}
info = []
t0 = time.time()
for a, b in zip(refit_idx[:-1], refit_idx[1:]):
    # fit on data <= a (index a is the refit date itself; targets need t+1+H <= a)
    tr = lr[:a + 1]
    ttr = mv.fwd_rv(tr, H)  # NaN where future not observable within tr
    seg = slice(a, b)

    # EWMA / rolling
    fc["ewma"][seg] = (H * mv.ewma_var(lr))[seg]
    fc["rv21"][seg] = (H * mv.past_rv(lr, 21))[seg]

    # GARCH / GJR
    for key, gjr in [("garch", False), ("gjr", True)]:
        p = mv.garch_fit(tr, gjr=gjr)
        fc[key][seg] = mv.garch_forecast(lr[:b], p, H)[seg]

    # HAR in logs over mug-shot horizons (day, week, month, quarter, year)
    ks = [1, 5, 21, 63, 252]
    X = np.vstack([np.log(mv.past_rv(lr[:b], k) + 1e-10) for k in ks]).T
    ok = np.isfinite(ttr) & np.all(np.isfinite(X[:a + 1]), axis=1)
    Xa = np.c_[np.ones(ok.sum()), X[:a + 1][ok]]
    ya = np.log(ttr[ok])
    coef, *_ = np.linalg.lstsq(Xa, ya, rcond=None)
    res = ya - Xa @ coef
    pred = np.c_[np.ones(len(X)), X] @ coef
    fc["har"][seg] = np.exp(pred + 0.5 * res.var())[seg]

    # MRW optimal linear predictor
    y = mv.logabs(tr)
    lam2, T = mv.mrw_logcov_fit(y)
    T = float(np.clip(T, 60, 5000))
    L = 1000
    w = mv.mrw_weights(lam2, T, L, H)
    mu = y.mean()
    s_all = mv.mrw_signal(mv.logabs(lr[:b]), w, mu)
    s_tr = s_all[:a + 1]
    ok = np.isfinite(ttr) & np.isfinite(s_tr)
    c = np.log(np.mean(ttr[ok] / np.exp(2 * s_tr[ok])))
    fc["mrw"][seg] = np.exp(c + 2 * s_all)[seg]
    A = np.c_[np.ones(ok.sum()), s_tr[ok]]
    cf, *_ = np.linalg.lstsq(A, np.log(ttr[ok]), rcond=None)
    rr = np.log(ttr[ok]) - A @ cf
    fc["mrw_free"][seg] = np.exp(cf[0] + cf[1] * s_all + 0.5 * rr.var())[seg]

    # Multi-timescale ARCH with / without leverage
    p = mv.mtarch_fit(tr, ttr, H=H)
    fc["mtarch"][seg] = mv.mtarch_forecast(lr[:b], p, H)[seg]
    p0 = dict(p)
    p0["g1"] = 0.0
    # refit without leverage for a fair comparison
    R2, R = mv.mtarch_features(tr)
    okm = np.isfinite(ttr) & np.all(np.isfinite(R2), axis=1)
    best = None
    for al in np.linspace(0.6, 1.6, 11):
        q2, _ = mv.mtarch_design(R2[okm], R[okm], al)
        Xm = np.c_[np.ones_like(q2), q2]
        yy = ttr[okm] / H
        wts = np.ones_like(yy)
        for _ in range(3):
            cm, *_ = np.linalg.lstsq(Xm * wts[:, None], yy * wts, rcond=None)
            f = np.maximum(Xm @ cm, 1e-8)
            wts = 1 / f
        ql = np.mean(yy / f - np.log(yy / f) - 1)
        if best is None or ql < best[0]:
            best = (ql, al, cm)
    fc["mtarch_nolev"][seg] = mv.mtarch_forecast(lr[:b], {"alpha": best[1], "s0": best[2][0],
                                                           "g2": best[2][1], "g1": 0.0}, H)[seg]
    info.append((dates[a].year, round(lam2, 4), round(T), p["alpha"], p["g1"] / p["g2"] if p["g2"] else 0))

print(f"{ASSET}: fitted in {time.time()-t0:.1f}s")
print("year, MRW lambda^2, T, mtarch alpha, g1/g2 (every 10y):")
for row in info[::10]:
    print("  ", row)

if DO_MSM:
    t1 = time.time()
    kbar = 6
    # MSM refit every 10 years (cost)
    for y0 in range(1950, 2000, 10):
        a = int(dates.searchsorted(pd.Timestamp(f"{y0}-01-01")))
        b = int(dates.searchsorted(pd.Timestamp(f"{y0+10}-01-01")))
        p = mv.msm_fit(lr[:a + 1], kbar=kbar)
        fc["msm"][a:b] = mv.msm_forecast(lr[:b], p, kbar, H)[a:b]
        print("  MSM", y0, np.round(p, 4), f"{time.time()-t1:.0f}s", flush=True)

sc = pd.DataFrame(fc, index=dates)
tg = pd.Series(target, index=dates)


def metrics(f, t):
    ok = np.isfinite(f) & np.isfinite(t) & (t > 0)
    f, t = f[ok], t[ok]
    ql = np.mean(t / f - np.log(t / f) - 1)
    lf, lt = np.log(f), np.log(t)
    r2 = np.corrcoef(lf, lt)[0, 1] ** 2
    bias = np.mean(lt - lf)
    return ql, r2, bias


rows = []
for k in fc:
    if np.all(np.isnan(fc[k])):
        continue
    row = {"model": k}
    for per, (a, b) in {"dev": ("1950", "1999"), "dev_a": ("1950", "1974"), "dev_b": ("1975", "1999")}.items():
        ql, r2, bias = metrics(sc[k].loc[a:b].to_numpy(), tg.loc[a:b].to_numpy())
        row[f"QL_{per}"] = round(ql, 4)
        row[f"R2_{per}"] = round(r2, 3)
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))
sc.to_pickle(f"/tmp/claude-0/-home-user-alpha/98ea3775-9ac1-5aa8-9c82-12ae31cc8668/scratchpad/fc_{ASSET}.pkl")
