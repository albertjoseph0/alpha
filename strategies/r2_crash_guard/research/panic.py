import sys; sys.path.insert(0, "strategies/r2_crash_guard/research")
import warnings; warnings.filterwarnings("ignore")
from lib import *
W = ("dev_a", "dev_b", "early")
M = mom(); m24 = LPM - LPM.shift(504)
vol = np.log1p(R["Mkt"]).rolling(126).std(); volmed = vol.rolling(2520, min_periods=756).median()
panic = (m24 < 0) & (vol > volmed)
NB = 36
blk = np.stack([(LP.shift(21*j) - LP.shift(21*(j+1))).to_numpy() for j in range(NB)], 0)
mb = np.stack([(LPM.shift(21*j) - LPM.shift(21*(j+1))).to_numpy() for j in range(NB)], 0)
tpos = {d: i for i, d in enumerate(cal)}
def beta(d):
    t = tpos[d]; x = mb[:, t]; y = blk[:, t, :]
    xc = x - x.mean(); b = (xc[:, None] * (y - y.mean(0))).sum(0) / (xc @ xc)
    return pd.Series(b, index=I49).where(VALID.loc[d]).dropna()
def base(d): return top_third(M.loc[d].where(VALID.loc[d]).dropna())
def mk(mix):
    def f(d):
        w = base(d)
        if panic.loc[d] and not np.isnan(mb[:, tpos[d]]).any():
            hb = top_third(beta(d)); w = pd.concat([w * (1 - mix), hb * mix]).groupby(level=0).sum()
        return w
    return f
print("panic months at decisions:", {w: int(panic.loc[FIRST].loc[WINDOWS[w][0]:WINDOWS[w][1]].sum()) for w in W})
for mix in ():
    r = run_weights(mk(mix), W)
    print(f"panic_highbeta mix={mix}", "  ".join(f"{w} {r[w].cagr:.2%}" for w in W), flush=True)
BW = {}
def betafloor(d):
    w = base(d)
    if np.isnan(mb[:, tpos[d]]).any(): return w
    b = beta(d); bw = float((w * b.reindex(w.index)).sum()); BW[d] = bw
    if bw >= 1: return w
    hb = top_third(b); bh_ = float(b[hb.index].mean())
    lam = min(1.0, (1 - bw) / (bh_ - bw))
    return pd.concat([w * (1 - lam), hb * lam]).groupby(level=0).sum()
r = {w: type("x",(),{"cagr":0})() for w in W}
print("betafloor1", "  ".join(f"{w} {r[w].cagr:.2%}" for w in W))
s = pd.Series(BW); 
for w in W:
    ss = s.loc[WINDOWS[w][0]:WINDOWS[w][1]]; print(w, f"winner beta mean {ss.mean():.2f}, frac<1 {np.mean(ss<1):.0%}")
rb = run_weights(base, W); rp = run_weights(mk(0.5), W)
pf = panic.loc[FIRST]
for w in W:
    a = rp[w].equity.resample("ME").last(); b = rb[w].equity.resample("ME").last()
    ex = (np.log(a).diff() - np.log(b).diff()).dropna()
    by = ex.groupby(ex.index.year).sum(); by = by[by.abs() > 1e-4]
    print(w, " ".join(f"{y}:{v:+.1%}" for y, v in by.items()))
