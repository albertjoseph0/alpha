"""Walk-forward ablation (dev 1950-99, same schedule as the harness: fit every 504 decision
days starting at the first decision date).  Records 5/21/63-day variance forecasts for Mkt,
scores out-of-sample QLIKE against realized variance and CAGR via simlib (== harness engine).
Variants: pretrain+finetune (final), scratch+finetune (no pretraining), pretrain zero-shot,
and EWMA baselines.  Usage: python ablation.py [variant ...]"""
import os, sys, json, time
os.environ["OMP_NUM_THREADS"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from simlib import sim, load_dev, WIN
import strategy as S
import ft_model as fm

d = load_dev()
cal = d.dates
k0 = cal.searchsorted(pd.Timestamp("1950-01-01")); kN = len(cal) - 1
dec = cal[k0 - 2: kN - 1]
lr = d.log_returns()["Mkt"].to_numpy()
C = fm.Corpus(lr[None, :])
t_idx = cal.get_indexer(dec)
ok = t_idx + 2 + 63 <= len(lr)
realized = {h: np.array([(C.cs[0, t + 2 + h] - C.cs[0, t + 2]) / h * 252 if t + 2 + h <= len(lr) else np.nan
                         for t in t_idx]) for h in fm.HORIZONS}
mu_by_date = pd.Series(np.nan, index=dec)

def qlike(fc, rv):
    m = np.isfinite(rv) & (rv > 0)
    y = np.log(rv[m] + 1e-12); yh = np.log(fc[m])
    return float(np.mean(np.exp(y - yh) + yh - y - 1))

def walk(strat):
    out = np.empty((len(dec), len(fm.HORIZONS))); mus = np.empty(len(dec))
    for b in range(0, len(dec), 504):
        strat.fit(d.until(dec[b]))
        blk = dec[b:b + 504]
        out[b:b + len(blk)] = strat.forecast_var(d.until(blk[-1]), blk)
        mus[b:b + len(blk)] = strat.mu
    return out, mus

def score(name, fc, mus, secs):
    res = {"variant": name, "secs": round(secs)}
    for j, h in enumerate(fm.HORIZONS):
        res[f"qlike{h}"] = round(qlike(fc[:, j], realized[h]), 4)
    w = pd.DataFrame({"Mkt": np.minimum(1.0, mus / fc[:, 1])}, index=dec)
    for win in WIN:
        res[win] = round(sim(w, d, win)[0], 4)
    res["avg_w"] = round(float(w["Mkt"].mean()), 3)
    print(json.dumps(res), flush=True)
    with open(os.path.join(HERE, "ablation_results.jsonl"), "a") as f:
        f.write(json.dumps(res) + "\n")
    np.save(os.path.join(HERE, f"fc_{name}.npy"), fc)

variants = sys.argv[1:] or ["ewma", "pretrain_ft", "scratch_ft", "pretrain_zeroshot"]
for v in variants:
    t0 = time.time()
    if v == "ewma":
        mus = np.array([S.FractalTransformer.__new__(S.FractalTransformer) and 0 for _ in dec], float)
        ex = (d.returns["Mkt"] - d.rf).expanding().mean().reindex(dec).to_numpy() * 252
        # piecewise-constant mu as in the strategy (updated every 504 days)
        mus = np.repeat(ex[::504], 504)[:len(dec)]
        for hl_j, hl in enumerate(fm.HALFLIVES[:4]):
            fc = np.exp(C.logv[hl_j][0, t_idx])[:, None].repeat(3, 1) * 252
            score(f"ewma{hl}", fc, mus, time.time() - t0)
        continue
    kw = dict(pretrain_ft=dict(), scratch_ft=dict(pretrain=False),
              pretrain_zeroshot=dict(finetune=False), scratch_ft_long=dict(pretrain=False))[v]
    if v == "scratch_ft_long":
        S.FT0_STEPS = 1800        # same total optimisation steps as pretrain (1500) + first FT (300)
    fc, mus = walk(S.FractalTransformer(**kw))
    score(v, fc, mus, time.time() - t0)
