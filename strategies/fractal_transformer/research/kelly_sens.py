"""Kelly-fraction sensitivity from saved walk-forward forecasts (no harness runs)."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
from simlib import sim, load_dev, WIN

HERE = os.path.dirname(os.path.abspath(__file__))
d = load_dev(); cal = d.dates
k0 = cal.searchsorted(pd.Timestamp("1950-01-01")); dec = cal[k0 - 2: len(cal) - 2]
ex = (d.returns["Mkt"] - d.rf).expanding().mean().reindex(dec).to_numpy() * 252
mus = np.repeat(ex[::504], 504)[:len(dec)]
rows = []
for v in ["ewma10", "ewma50", "pretrain_ft", "scratch_ft", "scratch_ft_long", "pretrain_zeroshot"]:
    f = os.path.join(HERE, f"fc_{v}.npy")
    if not os.path.exists(f):
        continue
    fc = np.load(f)[:, 1]
    for k in [1.0, 0.5]:
        w = pd.DataFrame({"Mkt": np.minimum(1, k * mus / fc)}, index=dec)
        rows.append([v, k] + [round(sim(w, d, x)[0], 4) for x in WIN] + [round(w.Mkt.mean(), 3)])
print(pd.DataFrame(rows, columns=["variant", "kelly", *WIN, "avg_w"]).to_string())
