"""Out-of-period regime check on dev-era data NOT used for choices: 1932-07 .. 1949-12."""
from sim import *  # noqa
from harness.engine import simulate
exec(open(os.path.join(HERE, "05_xs_h.py")).read().split("run(\"A: top4")[0].replace("print(\"rolling", "_=(\"rolling"))
z = np.load(os.path.join(HERE, "h_rel_robust_cache.npz")); Hlo = z["Hlo"]
zt = np.load(os.path.join(HERE, "h_ts_cache.npz")); Hlo_mkt = zt["Hlo"][:, 0]
S, E = pd.Timestamp("1932-07-01"), pd.Timestamp("1949-12-31")
def rel_mom(L):
    return np.array([cum[p + 1, 1:] - cum[p + 1 - L, 1:] - (cum[p + 1, 0] - cum[p + 1 - L, 0]) if p >= L else np.full(12, np.nan) for p in anchors])
rel12 = rel_mom(252)
abs12 = np.array([cum[p + 1, 1:] - cum[p + 1 - 252, 1:] if p >= 252 else np.full(12, np.nan) for p in anchors])
mkt12 = np.array([cum[p + 1, 0] - cum[p + 1 - 252, 0] if p >= 252 else np.nan for p in anchors])
def pre(label, Wa):
    W = to_daily(Wa)
    c = simulate(W, D, S, E).cagr
    eq = simulate(W, D, S, E).equity
    mdd = float((eq / eq.cummax() - 1).min())
    with open(LOG, "a") as f: f.write(f"PRE1950 {label}\t{c:+.4f}\n")
    print(f"{label:48s} 1932-49 CAGR {c:+.2%}  maxDD {mdd:+.1%}")
bh = np.zeros((len(anchors), 13)); bh[:, 0] = 1
pre("B&H Mkt", bh)
ew = np.zeros((len(anchors), 13)); ew[:, 1:] = 1 / 12
pre("EW industries", ew)
t1 = bh.copy(); t1[:, 0] = np.where(mkt12 < 0, 0, 1)
pre("T1 Mkt cash if 12m<0", t1)
pre("A top4 rel12", topk(rel12))
Hr = Hr5
pre("C-raw top4 rel12, raw rel-H>.5", topk(np.where(Hr > 0.5, rel12, np.where(rel12 > 0, 0.0, rel12))))
base = topk(np.where(Hlo > 0.5, rel12, np.where(rel12 > 0, 0.0, rel12)))
pre("C-lo top4 rel12, Lo rel-H>.5", base)
d1 = base.copy(); d1[:, 1:] = np.where(abs12 < 0, 0.0, d1[:, 1:])
pre("D1 C-lo + dual momentum", d1)
d2 = base.copy(); d2[:, 1:] = np.where((abs12 < 0) & (Hlo_mkt > 0.5)[:, None], 0.0, d2[:, 1:])
pre("D2 C-lo + dual mom if Mkt Lo-H>.5", d2)
