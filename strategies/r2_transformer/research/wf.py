"""Walk-forward research run: train rankers on a fixed 3-year calendar grid (Jan of years
divisible by 3, 1932..1998), record monthly weights for every variant 1932-1999, then score
each variant with the harness via a replay strategy (weights at month t use data <= t only).

usage: python research/wf.py [kinds=tf,lin]
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys, time, pathlib, json
import numpy as np, pandas as pd
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parents[2]))
import r2t_core as C
from harness import Strategy, run, I49
from harness.data import load

MIN_MONTHS = 120
data = load(until="1999-12-31")
dates = data.dates
R = data.extra[I49].to_numpy()
P = C.Prep(R, data.returns["Mkt"].to_numpy())
dec = np.flatnonzero(C.month_starts(dates))
dec = dec[dec >= C.LOOK]
F_all, V_all = C.features(P, dec)
rule_all = C.rule_weights(F_all, V_all)
grid_years = list(range(1932, 1999, 3))
grid_rows = [int(dates.searchsorted(pd.Timestamp(f"{y}-01-01"))) for y in grid_years]

kinds = sys.argv[1].split(",") if len(sys.argv) > 1 else ["tf", "lin"]
out = {"rule": rule_all}
for kind in kinds:
    Wm = np.full(rule_all.shape, np.nan)
    t0 = time.time()
    for gi, (y, g) in enumerate(zip(grid_years, grid_rows)):
        rows, G = C.labels(P, dec[dec <= g], g)
        nxt = grid_rows[gi + 1] if gi + 1 < len(grid_rows) else len(dates)
        sel = (dec >= g) & (dec < nxt)
        if len(rows) < MIN_MONTHS:
            continue
        q = np.searchsorted(dec, rows)
        mem = C.fit_ensemble(kind, F_all[q], V_all[q], G, seed0=y)
        Wm[sel] = C.ensemble_weights(mem, F_all[sel], V_all[sel])
        print(f"{kind} {y} n={len(rows)} {time.time()-t0:.0f}s", flush=True)
    out[kind] = Wm
np.savez(HERE / f"wf_{'_'.join(kinds)}.npz", dec=dec, **out)


class Replay(Strategy):
    refit_every = None
    def __init__(self, name, W):
        self.name = name
        self.W = pd.DataFrame(W, index=dates[dec], columns=I49)
    def predict(self, d, ds):
        out = pd.DataFrame(np.nan, index=ds, columns=I49)
        common = ds.intersection(self.W.index)
        out.loc[common] = self.W.loc[common].to_numpy()
        return out


def variants(out):
    rule = out["rule"]
    V = {"rule": rule}
    for k in kinds:
        W = out[k]
        miss = np.isnan(W).any(1)
        Wf = np.where(miss[:, None], rule, W)
        V[k] = Wf
        V[k + "_blend"] = 0.5 * Wf + 0.5 * rule
        V[k + "_top3"] = np.where(miss[:, None], rule, C.topk_weights(np.nan_to_num(W), V_all))
    return V


res = {}
for name, W in variants(out).items():
    res[name] = {w: run(Replay(name, W), window=w, data=data, ledger=False).cagr
                 for w in ("dev", "dev_a", "dev_b", "early")}
    to = np.abs(np.diff(W, axis=0)).sum(1).mean()
    hhi = (W ** 2).sum(1).mean()
    print(f"{name:12s} " + " ".join(f"{w}={c:+.2%}" for w, c in res[name].items())
          + f"  turnover/mo={to:.2f} 1/HHI={1/hhi:.1f}", flush=True)
json.dump(res, open(HERE / f"wf_{'_'.join(kinds)}.json", "w"), indent=1)
