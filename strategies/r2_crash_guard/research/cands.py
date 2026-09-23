import sys; sys.path.insert(0, "strategies/r2_crash_guard/research")
from lib import *
W = ("dev_a", "dev_b", "early")
M = mom()
m24 = LPM - LPM.shift(504)
# 21-day pseudo-months, j=0 most recent
NB = 36
blk = np.stack([(LP.shift(21*j) - LP.shift(21*(j+1))).to_numpy() for j in range(NB)], 0)       # NB x T x N
mb = np.stack([(LPM.shift(21*j) - LPM.shift(21*(j+1))).to_numpy() for j in range(NB)], 0)     # NB x T
VAL36 = (RI.notna().rolling(21*NB).sum() >= 21*NB - 2)
tpos = {d: i for i, d in enumerate(cal)}

def resid(d, scale=True):
    t = tpos[d]; y = blk[:, t, :]; x = mb[:, t]
    X = np.column_stack([np.ones(NB), x]); coef, *_ = np.linalg.lstsq(X, np.nan_to_num(y), rcond=None)
    e = np.nan_to_num(y) - X @ coef                  # NB x N
    s = e[1:12].sum(0)
    if scale: s = s / e[1:12].std(0, ddof=1)
    return pd.Series(s, index=I49).where(VAL36.loc[d]).dropna(), pd.Series(coef[1], index=I49)

def base(d): return top_third(M.loc[d].where(VALID.loc[d]).dropna())
def bear_half(d):
    w = base(d)
    if m24.loc[d] < 0: w = pd.concat([w * 0.5, pd.Series({"Mkt": 0.5})])
    return w
def dual(d):
    m = M.loc[d].where(VALID.loc[d]).dropna(); w = top_third(m)
    neg = [c for c in w.index if m[c] < 0]
    if neg: w = pd.concat([w.drop(neg), pd.Series({"Mkt": w[neg].sum()})])
    return w
def resmom(d):
    if np.isnan(mb[:, tpos[d]]).any(): return base(d)
    return top_third(resid(d, True)[0])
def resmom_raw(d):
    if np.isnan(mb[:, tpos[d]]).any(): return base(d)
    return top_third(resid(d, False)[0])
res = {}
for name, fn in [("base", base), ("resmom", resmom), ("resmom_raw", resmom_raw)]:
    r = run_weights(fn, W); res[name] = r
    print(f"{name:12s}", "  ".join(f"{w} {r[w].cagr:.2%}" for w in W), flush=True)
import pickle; pickle.dump({k: {w: v[w].equity for w in W} for k, v in res.items()}, open("/tmp/claude-0/-home-user-alpha/98ea3775-9ac1-5aa8-9c82-12ae31cc8668/scratchpad/eq1.pkl", "wb"))
print("configs", N_CONFIGS)
