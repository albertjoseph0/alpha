"""Cross-sectional content of industry tail features (descriptive).

At each month end, compute trailing features per industry and the Spearman rank IC with the
next month's return (skipping the 1-day execution lag). Report mean IC and t-stat per period.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from bt import data
from harness import INDUSTRIES

d = data()
R = d.returns
I = R[INDUSTRIES]
m = R["Mkt"]
dates = R.index
me = dates[(dates.to_series().dt.month != dates.to_series().shift(-1).dt.month).to_numpy()]
me = me[me >= pd.Timestamp("1928-07-01")]

WIN = 756  # 3y
Q = 0.05


def feats(t):
    k = dates.get_loc(t)
    X = I.iloc[k - WIN + 1:k + 1]
    mk = m.iloc[k - WIN + 1:k + 1]
    f = {}
    f["vol"] = X.std()
    f["downbeta"] = X[mk < mk.quantile(0.1)].mean() / mk[mk < mk.quantile(0.1)].mean()
    f["beta"] = X.apply(lambda c: np.cov(c, mk)[0, 1] / mk.var())
    # lower tail dependence with the other industries: P(i in own 5% tail | j in own 5% tail) avg over j
    thr = X.quantile(Q)
    E = (X < thr).astype(float)
    co = (E.T @ E).to_numpy() / E.sum().to_numpy()[None, :]
    np.fill_diagonal(co, np.nan)
    f["taildep"] = pd.Series(np.nanmean(co, axis=1), index=X.columns)
    # Hill left tail exponent (k = 5%)
    def hill(c):
        x = np.sort(-c.to_numpy())[::-1]
        kk = int(0.05 * len(x))
        return 1.0 / np.mean(np.log(x[:kk] / x[kk]))
    f["hill_alpha"] = X.apply(hill)
    # expected shortfall (5%) relative to vol
    f["es_over_vol"] = -X[X < thr].mean() / X.std()
    # momentum 12-1 month
    px = (1 + I.iloc[k - 252 + 1:k - 21 + 1]).prod()
    f["mom12_1"] = px
    f["mean3y"] = X.mean()
    return pd.DataFrame(f)


rows = []
for i, t in enumerate(me[:-1]):
    k = dates.get_loc(t)
    if k < WIN + 2:
        continue
    t2 = dates[min(k + 2, len(dates) - 1)]
    nxt = me[i + 1]
    k2 = dates.get_loc(nxt)
    fr = (1 + I.iloc[k + 2:k2 + 2]).prod() - 1
    F = feats(t)
    for c in F.columns:
        ic = spearmanr(F[c], fr).correlation
        rows.append((t, c, ic))
df = pd.DataFrame(rows, columns=["t", "feat", "ic"])
df["per"] = pd.cut(df["t"].dt.year, [1900, 1949, 1974, 1999], labels=["27-49", "50-74", "75-99"])
tab = df.groupby(["feat", "per"])["ic"].agg(["mean", "std", "count"])
tab["t"] = tab["mean"] / tab["std"] * np.sqrt(tab["count"])
print(tab.round(3).to_string())
