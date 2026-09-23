"""Does rolling H (5y weekly) predict next-month trend-following payoff?

Anchor = end of every 4th weekly block. Trend = sign of trailing L-day log return.
Payoff = sign * forward 20-day log return, starting after a 1-day lag.
"""
from common import *  # noqa

d, lr = get()
H = pd.read_pickle(os.path.join(HERE, "h_weekly_5y.pkl"))
pos = {dt: i for i, dt in enumerate(d.dates)}
cum = np.vstack([np.zeros((1, lr.shape[1])), np.cumsum(lr, axis=0)])
wk = block_sums(lr, 5)

def tr(p, L):  # trailing log return over rows (p-L, p]
    return cum[p + 1] - cum[max(p + 1 - L, 0)]

rows = []
for (dt, a), g in H.groupby(["date", "asset"]):
    p = pos[dt]
    if p + 22 >= len(lr):
        continue
    j = ASSETS.index(a)
    fwd = cum[p + 22, j] - cum[p + 2, j]
    # trailing 5y weekly lag-1..4 autocorr sum (plain short-memory persistence proxy)
    t = (p + 1) // 5
    x = wk[t - 260:t, j]
    x = x - x.mean()
    ac = sum(np.dot(x[k:], x[:-k]) for k in range(1, 5)) / np.dot(x, x)
    rows.append(dict(date=dt, asset=a, fwd=fwd, s3=np.sign(tr(p, 63)[j]), s6=np.sign(tr(p, 126)[j]),
                     s12=np.sign(tr(p, 252)[j]), ma=np.sign(np.log1p(d.returns.iloc[p][a]) * 0 + (cum[p + 1, j] - (cum[p + 1 - 200:p + 1, j]).mean())),
                     ac4=ac, **g.iloc[0][["rs", "dfa", "vt", "loV", "dfa_abs"]].to_dict()))
P = pd.DataFrame(rows)
P["yr"] = P.date.dt.year
for s in ["s3", "s6", "s12", "ma"]:
    P["pay_" + s] = P[s] * P.fwd
P.to_pickle(os.path.join(HERE, "panel.pkl"))

def report(P, label):
    print(f"\n=== {label}: n={len(P)}  ({P.date.min().year}-{P.date.max().year})")
    print("mean monthly payoff x1e4 of trend rules (all):",
          {s: round(P['pay_' + s].mean() * 1e4, 1) for s in ['s3', 's6', 's12', 'ma']},
          " long-only fwd:", round(P.fwd.mean() * 1e4, 1))
    for h in ["rs", "dfa", "vt", "loV", "ac4", "dfa_abs"]:
        q = P.groupby(["date"])[h].rank(pct=True)  # cross-sectional rank at each date
        lo_, hi_ = P[q <= 1/3], P[q > 2/3]
        # time-series rule: absolute threshold (H>0.5 or V>E[V], ac>0)
        thr = {"loV": np.sqrt(np.pi / 2), "ac4": 0.0}.get(h, 0.5)
        if h == "dfa_abs":
            thr = P[h].median()
        up, dn = P[P[h] > thr], P[P[h] <= thr]
        out = []
        for s in ["s6", "s12", "ma"]:
            c = "pay_" + s
            out.append(f"{s}: xs-lo {lo_[c].mean()*1e4:5.1f} xs-hi {hi_[c].mean()*1e4:5.1f} | H>thr {up[c].mean()*1e4:5.1f}(n{len(up)}) H<=thr {dn[c].mean()*1e4:5.1f}")
        # rank-IC style: corr(H, payoff) pooled
        ic = P[[h, "pay_s12"]].corr().iloc[0, 1]
        print(f" {h:7s} corr(H,pay12)={ic:+.3f} | " + " || ".join(out))

report(P, "all 13 assets")
report(P[P.date.dt.year < 1950], "pre-1950")
report(P[(P.date.dt.year >= 1950) & (P.date.dt.year < 1975)], "1950-74")
report(P[P.date.dt.year >= 1975], "1975-99")
report(P[P.asset == "Mkt"], "Mkt only")
