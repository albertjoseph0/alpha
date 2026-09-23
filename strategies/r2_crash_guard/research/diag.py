import sys; sys.path.insert(0, "strategies/r2_crash_guard/research")
from lib import *
M = mom()
def base(d):
    m = M.loc[d].where(VALID.loc[d]).dropna(); return top_third(m)
W = ("dev_a", "dev_b", "early")
b = run_weights(base, W); h = bh(W)
for w in W: print(w, f"base {b[w].cagr:.2%}  bh {h[w].cagr:.2%}")
# state at each decision date
m24 = (LPM - LPM.shift(504))
vol = np.log1p(R["Mkt"]).rolling(126).std() * np.sqrt(252)
volmed = vol.rolling(252*10, min_periods=252*3).median()
for w in W:
    eb, eh = b[w].equity, h[w].equity
    mb = eb.resample("ME").last().pct_change(); mh = eh.resample("ME").last().pct_change()
    # state known at start of month: use last decision date info of previous month end
    st = pd.DataFrame({"bear": m24 < 0, "hv": vol > volmed}).resample("ME").last().shift(1).reindex(mb.index)
    ex = np.log1p(mb) - np.log1p(mh)
    df = pd.DataFrame({"ex": ex, "mkt": mh, "bear": st.bear, "hv": st.hv}).dropna()
    yrs = df.index[-1].year - df.index[0].year + 1
    print(f"\n{w}: total log excess/yr {df.ex.sum()/yrs:+.2%}")
    for name, g in df.groupby(["bear", "hv"]):
        print(f"  bear={name[0]!s:5} hv={name[1]!s:5} n={len(g):3d}  ex_sum/yr={g.ex.sum()/yrs:+.2%}  ex/mo={g.ex.mean():+.2%}  mkt/mo={g.mkt.mean():+.2%}")
    # bear months split by market up/down
    bb = df[df.bear]
    print("  bear & mkt up month: n=%d ex/mo=%+.2f%%; bear & mkt down: n=%d ex/mo=%+.2f%%" % (
        (bb.mkt>0).sum(), 100*bb.ex[bb.mkt>0].mean(), (bb.mkt<=0).sum(), 100*bb.ex[bb.mkt<=0].mean()))
    ya = (1+mb).groupby(mb.index.year).prod()-1; yh=(1+mh).groupby(mh.index.year).prod()-1
    rel = (ya-yh).sort_values()
    print("  worst yrs:", ", ".join(f"{y}:{r:+.1%}(mkt {yh[y]:+.0%})" for y, r in rel.head(6).items()))
