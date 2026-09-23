import pickle, numpy as np, pandas as pd, os
os.environ["OMP_NUM_THREADS"]="1"
from harness.data import load
D = load(until="1999-12-31"); mk = D.returns["Mkt"]; rf = D.rf
eq = pickle.load(open("/tmp/claude-0/-home-user-alpha/98ea3775-9ac1-5aa8-9c82-12ae31cc8668/scratchpad/eq1.pkl", "rb"))["base"]
lpm = np.log1p(mk).cumsum(); m24 = (lpm - lpm.shift(504)).resample("ME").last().shift(1)
for w, e in eq.items():
    p = e.resample("ME").last().pct_change().dropna()
    m = (1+mk).resample("ME").prod().sub(1).reindex(p.index); f = (1+rf).resample("ME").prod().sub(1).reindex(p.index)
    y, x = p - f, m - f
    b, a = np.polyfit(x, y, 1)
    up = x > x.quantile(0.9)
    ex = np.log1p(p) - np.log1p(m)
    bear = (m24.reindex(p.index) < 0)
    # beta in bear-state months
    bb = np.polyfit(x[bear], y[bear], 1)[0] if bear.sum() > 5 else np.nan
    print(f"{w}: beta {b:.2f} alpha/mo {a:+.2%} | top-decile mkt months n={up.sum()} ex/mo {ex[up].mean():+.2%} (sum/yr {ex[up].sum()/len(p)*12:+.2%}) | beta bear-state {bb:.2f} (n={bear.sum()})")
