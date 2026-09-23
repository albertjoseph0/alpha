"""Variant C with stale-price-robust relative H: AR(1)-prewhitened, Lo q=4, and
a shuffle-referenced H (Mandelbrot's shuffle test: H - mean H of shuffled copies)."""
from sim import *  # noqa
exec(open(os.path.join(HERE, "05_xs_h.py")).read().split("run(\"A: top4")[0].replace("print(\"rolling", "_=(\"rolling"))
from hurst import lo_hurst

def prewhiten(x):
    x = x - x.mean()
    phi = np.dot(x[1:], x[:-1]) / np.dot(x[:-1], x[:-1])
    return x[1:] - phi * x[:-1]

def h3(x):
    return np.mean([rs_hurst(x, [8, 13, 26, 52, 65, 130]), dfa_hurst(x, [8, 13, 26, 52]), vt_hurst(x, [2, 4, 8, 13, 26])])

cache = os.path.join(HERE, "h_rel_robust_cache.npz")
if os.path.exists(cache):
    z = np.load(cache); Hpw, Hlo = z["Hpw"], z["Hlo"]
else:
    Hpw = np.full((len(anchors), 12), np.nan); Hlo = Hpw.copy()
    for i, p in enumerate(anchors):
        t = (p + 1) // 5
        if t < 260: continue
        x = wk_rel[t - 260:t]
        for j in range(12):
            Hpw[i, j] = h3(prewhiten(x[:, j])); Hlo[i, j] = lo_hurst(x[:, j], 4)
    np.savez(cache, Hpw=Hpw, Hlo=Hlo)
yrs = idx[anchors].year
for nm, H in [("raw", Hr5), ("prewhitened", Hpw), ("Lo", Hlo)]:
    s = pd.Series(np.nanmean(H, axis=1), index=yrs)
    print(f"rel-H {nm}: mean by decade", s.groupby(s.index // 10 * 10).mean().round(3).to_dict(),
          f" frac>0.5 (1950-99) {np.nanmean(H[yrs >= 1950] > 0.5):.2f}")

def rel_mom(L):
    return np.array([cum[p + 1, 1:] - cum[p + 1 - L, 1:] - (cum[p + 1, 0] - cum[p + 1 - L, 0]) if p >= L else np.full(12, np.nan) for p in anchors])
def C_score(H, m, thr=0.5):
    return np.where(H > thr, m, np.where(m > 0, 0.0, m))
rel12 = rel_mom(252)
def run(label, Wa):
    W = to_daily(Wa); o = score(W, label)
    print(fmt(label, o, f"turn/yr {turnover(W):.2f}"), flush=True)
run("C-pw: prewhitened rel-H > 0.5", topk(C_score(Hpw, rel12)))
run("C-lo: Lo rel-H > 0.5", topk(C_score(Hlo, rel12)))
med = np.nanmedian(Hr5, axis=1, keepdims=True)
run("C-xsmed: raw rel-H > cross-sectional median", topk(C_score(Hr5, rel12, med)))
