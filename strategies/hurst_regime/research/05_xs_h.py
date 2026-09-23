"""Cross-sectional industry trend with/without H conditioning (pre-declared variants)."""
from sim import *  # noqa
from hurst import rs_hurst, dfa_hurst, vt_hurst

R = D.returns[ASSETS]
lr = np.log1p(R).to_numpy()
n = len(lr)
idx = D.dates
IND = ASSETS[1:]
cum = np.vstack([np.zeros((1, 13)), np.cumsum(lr, axis=0)])
anchors = np.arange(20, n, 21)
rel = lr[:, 1:] - lr[:, [0]]
wk_rel = block_sums(rel, 5)
wk_raw = block_sums(lr[:, 1:], 5)

def rolling_h(wk, Wn, p):
    t = (p + 1) // 5
    if t < Wn:
        return np.full(wk.shape[1], np.nan)
    x = wk[t - Wn:t]
    out = []
    for j in range(x.shape[1]):
        xj = x[:, j]
        sc_rs = [8, 13, 26, 52, 65, 130] if Wn <= 260 else [13, 26, 52, 65, 130, 260]
        out.append(np.mean([rs_hurst(xj, sc_rs), dfa_hurst(xj, [8, 13, 26, 52]), vt_hurst(xj, [2, 4, 8, 13, 26])]))
    return np.array(out)

cache = os.path.join(HERE, "h_xs_cache.npz")
if os.path.exists(cache):
    z = np.load(cache); Hr5, Hr10, Ha5 = z["Hr5"], z["Hr10"], z["Ha5"]
else:
    Hr5 = np.array([rolling_h(wk_rel, 260, p) for p in anchors])
    Hr10 = np.array([rolling_h(wk_rel, 520, p) for p in anchors])
    Ha5 = np.array([rolling_h(wk_raw, 260, p) for p in anchors])
    np.savez(cache, Hr5=Hr5, Hr10=Hr10, Ha5=Ha5)
print("rolling rel-H 5y: mean %.3f sd %.3f; 10y: mean %.3f sd %.3f" % (np.nanmean(Hr5), np.nanstd(Hr5), np.nanmean(Hr10), np.nanstd(Hr10)))

def to_daily(Wa):
    W = pd.DataFrame(np.nan, idx, ASSETS)
    W.iloc[anchors] = Wa
    return W.ffill().fillna(0.0)

def run(label, Wa):
    W = to_daily(Wa)
    o = score(W, label)
    print(fmt(label, o, f"turn/yr {turnover(W):.2f}"), flush=True)

K = 4
mom12 = np.array([cum[p + 1, 1:] - cum[p + 1 - 252, 1:] if p >= 252 else np.full(12, np.nan) for p in anchors])

def topk(score_, k=K):
    Wa = np.zeros((len(anchors), 13))
    for i, s in enumerate(score_):
        if np.all(np.isnan(s)):
            continue
        s = np.where(np.isnan(s), -np.inf, s)
        top = np.argsort(-s, kind="stable")[:k]
        Wa[i, 1 + top] = 1.0 / k
    return Wa

run("A: top4 by 12m mom", topk(mom12))
# B: fBm predictor: score = beta(H) * trailing return, H per industry (rel, 5y)
def beta(H, L=12.0, h=1.0):
    return ((L + h) ** (2 * H) - L ** (2 * H) - h ** (2 * H)) / (2 * L ** (2 * H))
mkt12 = mom12 - 0  # industry absolute 12m
rel12 = np.array([cum[p + 1, 1:] - cum[p + 1 - 252, 1:] - (cum[p + 1, 0] - cum[p + 1 - 252, 0]) if p >= 252 else np.full(12, np.nan) for p in anchors])
run("B: top4 by beta(H_rel5y)*rel12m (sign flips if H<.5)", topk(beta(Hr5) * rel12))
run("B10: top4 by beta(H_rel10y)*rel12m", topk(beta(Hr10) * rel12))
# C: filter: require H_rel>0.5 to count as persistent; non-persistent industries get score 0 (neutral)
run("C: top4 by mom12, only among H_rel5y>0.5 (else rank 0)", topk(np.where(Hr5 > 0.5, rel12, np.where(rel12 > 0, 0.0, rel12))))
# D: ranking by H alone (does persistence itself earn?)
run("D: top4 by H_rel5y alone", topk(Hr5))
# E: raw-return H (5y) as tie: mom12 * (H_raw - 0.5) sign
run("E: top4 by mom12 * (2*H_raw5y-1)", topk(mom12 * (2 * Ha5 - 1)))
