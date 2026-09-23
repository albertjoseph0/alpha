"""Cross-sectional structure among the 12 industries (research only)."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
from harness import load_dev
from harness.data import INDUSTRIES

d = load_dev()
lr = np.log1p(d.returns)
h = 21
fwd = lr[INDUSTRIES].rolling(h).sum().shift(-(h + 1))          # t+2 .. t+h+1
vol = lr[INDUSTRIES].rolling(126).std()
feats = {
    "mom12_1": lr[INDUSTRIES].rolling(231).sum().shift(21),
    "mom6": lr[INDUSTRIES].rolling(126).sum(),
    "rev1m": -lr[INDUSTRIES].rolling(21).sum(),
    "lowvol": -vol,
    "zmom12": lr[INDUSTRIES].rolling(252).sum() / (vol * np.sqrt(252)),
}
for per, (a, b) in {"27-49": ("1927", "1949"), "50-74": ("1950", "1974"), "75-99": ("1975", "1999")}.items():
    out = []
    for name, f in feats.items():
        F = f.loc[a:b]; Y = fwd.loc[a:b]
        idx = F.dropna().index.intersection(Y.dropna().index)[::21]
        ic = [pd.Series(F.loc[t]).rank().corr(pd.Series(Y.loc[t]).rank()) for t in idx]
        # top-3 minus average, annualised
        spread = []
        for t in idx:
            top = F.loc[t].nlargest(3).index
            spread.append(Y.loc[t, top].mean() - Y.loc[t].mean())
        out.append((name, np.mean(ic), np.mean(ic) / np.std(ic) * np.sqrt(len(ic)), np.mean(spread) * 12))
    print(per, "  ".join(f"{n}: IC={ic:+.3f} t={t:+.1f} top3-avg={s:+.3f}" for n, ic, t, s in out))
