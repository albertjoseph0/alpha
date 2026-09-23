"""Final candidate: pooled 10y relative-H gate. If mean over industries of H_rel (10y weekly,
avg RS/DFA/VT) > 0.5 -> top4 by rel 12m; else equal-weight industries."""
from sim import *  # noqa
from harness.engine import simulate
exec(open(os.path.join(HERE, "05_xs_h.py")).read().split("run(\"A: top4")[0].replace("print(\"rolling", "_=(\"rolling"))
rel12 = np.array([cum[p + 1, 1:] - cum[p + 1 - 252, 1:] - (cum[p + 1, 0] - cum[p + 1 - 252, 0]) if p >= 252 else np.full(12, np.nan) for p in anchors])
pooled = np.nanmean(Hr10, axis=1)
yrs = idx[anchors].year
s = pd.Series(pooled, index=yrs)
print("pooled rel-H 10y by decade:", s.groupby(s.index // 10 * 10).mean().round(3).to_dict(), " min", np.nanmin(pooled).round(3))
print("fraction gate ON 1950-99:", np.mean(pooled[yrs >= 1950] > 0.5), " 1936-49:", np.nanmean(pooled[(yrs >= 1936) & (yrs < 1950)] > 0.5))
A = topk(rel12)
ew = np.zeros((len(anchors), 13)); ew[:, 1:] = 1 / 12
G = np.where((pooled > 0.5)[:, None], A, ew)
o = score(to_daily(G), "G pooled rel-H10y gate: top4 rel12 else EW")
print(fmt("G gate", o))
c = simulate(to_daily(G), D, pd.Timestamp("1936-07-01"), pd.Timestamp("1949-12-31")).cagr
a = simulate(to_daily(A), D, pd.Timestamp("1936-07-01"), pd.Timestamp("1949-12-31")).cagr
print(f"1936-49: G {c:+.2%}  A {a:+.2%}")
