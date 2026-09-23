import sys; sys.path.insert(0, "strategies/r2_crash_guard/research")
import warnings; warnings.filterwarnings("ignore")
from lib import *
W = ("dev_a", "dev_b", "early")
M = mom()
def base(d): return top_third(M.loc[d].where(VALID.loc[d]).dropna())
# daily active return of the (point-in-time) winner basket vs Mkt, over past 126 days, recomputed each month
TE_hist = {}
RIf = RI.fillna(0); tpos = {d: i for i, d in enumerate(cal)}
def te_scaled(d):
    w = base(d); t = tpos[d]
    act = RIf.iloc[t-125:t+1][w.index].mean(1) - R["Mkt"].iloc[t-125:t+1]
    te = float(act.std()); TE_hist[d] = te
    hist = pd.Series(TE_hist); hist = hist[hist.index <= d].iloc[-120:]   # trailing 10y of monthly TE estimates
    if len(hist) < 36: return w
    lam = min(1.0, float(hist.median()) / te)
    return pd.concat([w * lam, pd.Series({"Mkt": 1 - lam})]).groupby(level=0).sum()
r = run_weights(te_scaled, W)
print("te_scaled", "  ".join(f"{w} {r[w].cagr:.2%}" for w in W))
