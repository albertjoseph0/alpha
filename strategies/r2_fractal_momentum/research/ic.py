import os, sys, warnings; warnings.filterwarnings("ignore")
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from signals import signal, win, tsum, trailing_sigma
from harness import I49
from harness.data import load

d = load(until="1999-12-31"); R = d.tradeable_returns()[I49]
valid = (R.notna().rolling(252).sum() >= 250).to_numpy()
r = np.log1p(R.fillna(0).to_numpy(np.float64)); T = len(r)
S = {k: signal(k, r) for k in ["mom", "jw3", "noah3", "eff5", "tt1"]}
L5 = win(np.nan_to_num(np.abs(tsum(r, 5))), 248) / 5
L21 = win(np.nan_to_num(np.abs(tsum(r, 21))), 232) / 21
S["D_21_5"] = 1 - np.log(L21 / L5) / np.log(21 / 5)          # divider dimension from two rulers
S["vol"] = trailing_sigma(r)
fwd = np.full(r.shape, np.nan); c = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(r, 0)])
fwd[:T - 23] = c[23:T] - c[2:T - 21]                            # t+2 .. t+22 (execution lag)
dates = d.dates; first = np.r_[True, dates.month[1:] != dates.month[:-1]]
idx = np.where(first)[0]
def ic(a, b):
    m = ~np.isnan(a) & ~np.isnan(b); 
    return pd.Series(a[m]).rank().corr(pd.Series(b[m]).rank()) if m.sum() > 10 else np.nan
# residual of X on mom rank (cross-sectional OLS on ranks)
def resid(x, y):
    m = ~np.isnan(x) & ~np.isnan(y); out = np.full_like(x, np.nan)
    if m.sum() < 10: return out
    xr, yr = pd.Series(x[m]).rank().values, pd.Series(y[m]).rank().values
    b = np.polyfit(yr, xr, 1); out[m] = xr - np.polyval(b, yr); return out
rows = []
for i in idx:
    if i + 23 >= T: continue
    v = valid[i]; f = np.where(v, fwd[i], np.nan)
    rec = {"date": dates[i]}
    for k, s in S.items():
        x = np.where(v, s[i], np.nan); rec[k] = ic(x, f)
        if k != "mom": rec[k + "|mom"] = ic(resid(x, np.where(v, S["mom"][i], np.nan)), f)
    rows.append(rec)
df = pd.DataFrame(rows).set_index("date")
per = {"early": ("1932", "1949"), "dev_a": ("1950", "1974"), "dev_b": ("1975", "1999")}
out = pd.DataFrame({p: df.loc[a:b].mean() for p, (a, b) in per.items()})
tst = pd.DataFrame({p + "_t": df.loc[a:b].mean() / df.loc[a:b].std() * np.sqrt(len(df.loc[a:b])) for p, (a, b) in per.items()})
print(pd.concat([out, tst], axis=1).round(3).to_string())
