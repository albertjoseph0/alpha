"""Placebo for variant C: H series circularly shifted per industry (keeps H's marginal
distribution and autocorrelation, destroys its timing). Also robustness of C vs A over K and lookback."""
from sim import *  # noqa
import importlib.util
exec(open(os.path.join(HERE, "05_xs_h.py")).read().split("run(\"A: top4")[0].replace("print(\"rolling", "_=(\"rolling"))

def rel_mom(L):
    return np.array([cum[p + 1, 1:] - cum[p + 1 - L, 1:] - (cum[p + 1, 0] - cum[p + 1 - L, 0]) if p >= L else np.full(12, np.nan) for p in anchors])

def C_score(H, m):
    return np.where(H > 0.5, m, np.where(m > 0, 0.0, m))

def cagr(Wa, label, log=True):
    return score(to_daily(Wa), label, log=log)

rng = np.random.default_rng(7)
rel12 = rel_mom(252)
base = cagr(topk(rel12), "A-rel: top4 by rel12 (same ranking as A)")
realC = cagr(topk(C_score(Hr5, rel12)), "C real (dup)", log=False)
print("A", {k: f"{v:+.2%}" for k, v in base.items()}, " C", {k: f"{v:+.2%}" for k, v in realC.items()})
pl = []
valid = ~np.isnan(Hr5[:, 0])
iv = np.where(valid)[0]
for b in range(60):
    Hs = Hr5.copy()
    for j in range(12):
        sh = rng.integers(60, len(iv) - 60)
        Hs[iv, j] = np.roll(Hr5[iv, j], sh)
    pl.append(cagr(topk(C_score(Hs, rel12)), f"placebo C {b}", log=False))
with open(LOG, "a") as f:
    f.write("placebo C x60 (not selection)\n")
P = pd.DataFrame(pl)
print("placebo C: mean", P.mean().map("{:+.2%}".format).to_dict(), " 90th pct", P.quantile(0.9).map("{:+.2%}".format).to_dict(),
      " frac >= real:", {k: float((P[k] >= realC[k]).mean()) for k in P})

print("\nRobustness grid (C - A, dev):")
for L in [126, 252]:
    m = rel_mom(L)
    for k in [3, 4, 6]:
        a = cagr(topk(m, k), f"grid A L{L} k{k}")
        c = cagr(topk(C_score(Hr5, m), k), f"grid C L{L} k{k}")
        print(f" L={L} k={k}:  A {a['dev']:+.2%}  C {c['dev']:+.2%}  diff {c['dev']-a['dev']:+.2%} | dev_a {c['dev_a']-a['dev_a']:+.2%} dev_b {c['dev_b']-a['dev_b']:+.2%}")
