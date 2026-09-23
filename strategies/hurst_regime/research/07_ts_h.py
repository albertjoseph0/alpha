"""Time-series dimension: market-level H regime gating a defensive (cash) switch.
Also: stale-price-robust H (AR(1) pre-whitened weekly; long-scale-only)."""
from sim import *  # noqa
from hurst import rs_hurst, dfa_hurst, vt_hurst, lo_hurst

R = D.returns[ASSETS]
lr = np.log1p(R).to_numpy()
n = len(lr); idx = D.dates
cum = np.vstack([np.zeros((1, 13)), np.cumsum(lr, axis=0)])
anchors = np.arange(20, n, 21)
wk = block_sums(lr, 5)

def prewhiten(x):
    x = x - x.mean()
    phi = np.dot(x[1:], x[:-1]) / np.dot(x[:-1], x[:-1])
    return x[1:] - phi * x[:-1]

def h3(x, long_only=False):
    if long_only:   # scales >= 13 weeks only: insensitive to short-lag (stale-price) autocorr
        return np.mean([rs_hurst(x, [13, 26, 52, 65, 130]), dfa_hurst(x, [13, 26, 52, 65]), vt_hurst(x, [13, 26, 52]) - 0.5 * np.log(max(1e-9, 1)) ])
    return np.mean([rs_hurst(x, [8, 13, 26, 52, 65, 130]), dfa_hurst(x, [8, 13, 26, 52]), vt_hurst(x, [2, 4, 8, 13, 26])])

cache = os.path.join(HERE, "h_ts_cache.npz")
if os.path.exists(cache):
    z = np.load(cache); Hw, Hpw, Hlo = z["Hw"], z["Hpw"], z["Hlo"]
else:
    Hw = np.full((len(anchors), 13), np.nan); Hpw = Hw.copy(); Hlo = Hw.copy()
    for i, p in enumerate(anchors):
        t = (p + 1) // 5
        if t < 260: continue
        x = wk[t - 260:t]
        for j in range(13):
            Hw[i, j] = h3(x[:, j]); Hpw[i, j] = h3(prewhiten(x[:, j])); Hlo[i, j] = lo_hurst(x[:, j], 4)
    np.savez(cache, Hw=Hw, Hpw=Hpw, Hlo=Hlo)
yrs = idx[anchors].year
for nm, H in [("weekly", Hw), ("prewhitened", Hpw), ("Lo q=4", Hlo)]:
    s = pd.Series(np.nanmean(H, axis=1), index=yrs)
    print(f"market-wide mean H ({nm}) by decade:", s.groupby(s.index // 10 * 10).mean().round(3).to_dict())

def to_daily(Wa):
    W = pd.DataFrame(np.nan, idx, ASSETS); W.iloc[anchors] = Wa
    return W.ffill().fillna(0.0)

def run(label, Wa):
    W = to_daily(Wa); o = score(W, label)
    print(fmt(label, o, f"turn/yr {turnover(W):.2f} inv {W.abs().sum(axis=1).mean():.2f}"), flush=True)

mkt12 = np.array([cum[p + 1, 0] - cum[p + 1 - 252, 0] if p >= 252 else np.nan for p in anchors])
invest = np.ones(len(anchors))
Hm = {"w": np.nanmean(Hw, axis=1), "pw": np.nanmean(Hpw, axis=1), "lo": np.nanmean(Hlo, axis=1),
      "mkt_w": Hw[:, 0], "mkt_pw": Hpw[:, 0]}
def mkt_w(expo):
    Wa = np.zeros((len(anchors), 13)); Wa[:, 0] = expo; return Wa
down = mkt12 < 0
run("T0 B&H (anchored)", mkt_w(invest))
run("T1 Mkt: cash if 12m<0", mkt_w(np.where(down, 0.0, 1.0)))
for k, h in Hm.items():
    gate = h > 0.5
    run(f"T2[{k}] Mkt: cash if 12m<0 AND H>0.5", mkt_w(np.where(down & gate, 0.0, 1.0)))
    frac = np.nanmean(gate[yrs >= 1950])
    print(f"      fraction of anchors with H>0.5 (1950-99): {frac:.2f}")
