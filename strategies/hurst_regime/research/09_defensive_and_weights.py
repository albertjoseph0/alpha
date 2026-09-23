"""On top of C-lo (top4 by rel 12m, Lo rel-H>0.5 filter):
 D1 dual momentum: selected industry with abs 12m return < 0 -> its slot to cash
 D2 H-gated dual momentum: slot to cash only if also market Lo-H > 0.5 (persistent regime)
 V1 inverse-vol weights among the 4 (vol = mean of 21/63/252d realized vol: long-memory proxy)
"""
from sim import *  # noqa
exec(open(os.path.join(HERE, "05_xs_h.py")).read().split("run(\"A: top4")[0].replace("print(\"rolling", "_=(\"rolling"))
z = np.load(os.path.join(HERE, "h_rel_robust_cache.npz")); Hlo = z["Hlo"]
zt = np.load(os.path.join(HERE, "h_ts_cache.npz")); Hlo_mkt = zt["Hlo"][:, 0]

def rel_mom(L):
    return np.array([cum[p + 1, 1:] - cum[p + 1 - L, 1:] - (cum[p + 1, 0] - cum[p + 1 - L, 0]) if p >= L else np.full(12, np.nan) for p in anchors])
rel12 = rel_mom(252)
abs12 = np.array([cum[p + 1, 1:] - cum[p + 1 - 252, 1:] if p >= 252 else np.full(12, np.nan) for p in anchors])
sc = np.where(Hlo > 0.5, rel12, np.where(rel12 > 0, 0.0, rel12))
base = topk(sc)
def run(label, Wa):
    W = to_daily(Wa); o = score(W, label)
    print(fmt(label, o, f"turn/yr {turnover(W):.2f} gross {W.abs().sum(axis=1).mean():.2f}"), flush=True)
run("C-lo (dup, reference)", base)
d1 = base.copy(); d1[:, 1:] = np.where(abs12 < 0, 0.0, d1[:, 1:])
run("D1 dual momentum (abs12<0 -> cash)", d1)
d2 = base.copy(); gate = (Hlo_mkt > 0.5)[:, None]
d2[:, 1:] = np.where((abs12 < 0) & gate, 0.0, d2[:, 1:])
run("D2 dual momentum only if Mkt Lo-H>0.5", d2)
sq = lr[:, 1:] ** 2
csq = np.vstack([np.zeros((1, 12)), np.cumsum(sq, axis=0)])
vol = np.array([np.mean([np.sqrt((csq[p + 1] - csq[p + 1 - L]) / L) for L in (21, 63, 252)], axis=0) if p >= 252 else np.full(12, np.nan) for p in anchors])
v1 = base.copy()
sel = v1[:, 1:] > 0
iv = np.where(sel, 1.0 / vol, 0.0)
v1[:, 1:] = np.where(sel.any(axis=1, keepdims=True), iv / np.maximum(iv.sum(axis=1, keepdims=True), 1e-12), 0.0)
run("V1 inverse-vol weights among selected", v1)
