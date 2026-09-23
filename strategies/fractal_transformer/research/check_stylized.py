"""Compare stylized facts of the synthetic generators with the real dev data (research only)."""
import os, sys, time
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from harness import load_dev
import ft_sim

def facts(r):
    r = r - r.mean()
    a = np.abs(r); s = r.std()
    kurt = ((r / s) ** 4).mean()
    m = r[: len(r) // 21 * 21].reshape(-1, 21).sum(1)
    kurt_m = (((m - m.mean()) / m.std()) ** 4).mean()
    ac = lambda x, k: np.corrcoef(x[:-k], x[k:])[0, 1]
    acabs = [ac(a, k) for k in (1, 10, 50, 150)]
    # leverage: corr(r_t, sum_{j=1..21} r^2_{t+j})
    fut = np.convolve(r ** 2, np.ones(21), "valid")[1:]
    lev = np.corrcoef(r[: len(fut)], fut)[0, 1]
    x = np.sort(a)[::-1][: int(0.01 * len(a))]
    hill = 1.0 / np.mean(np.log(x[:-1] / x[-1]))
    return dict(kurt=kurt, kurt_m=kurt_m, ac1=ac(r, 1), acabs1=acabs[0], acabs10=acabs[1],
                acabs50=acabs[2], acabs150=acabs[3], lev21=lev, hill1pct=hill)

import pandas as pd
d = load_dev()
rows = {}
for c in ["Mkt", "Utils", "BusEq"]:
    for per, sl in [("26-49", slice("1926", "1949")), ("50-99", slice("1950", "1999"))]:
        rows[f"real {c} {per}"] = facts(np.log1p(d.returns[c][sl].to_numpy()))
t = time.time()
rng = np.random.default_rng(0)
n = 12000
for name, fn in [("MRW+lev", ft_sim.mrw_leverage), ("ZB-ARCH", ft_sim.zumbach_arch), ("MMAR", ft_sim.mmar_cascade)]:
    t0 = time.time(); R = fn(rng, 12, n); dt = time.time() - t0
    F = pd.DataFrame([facts(x) for x in R]).median()
    rows[f"{name} (med of 12, {dt:.1f}s)"] = F.to_dict()
R = ft_sim.generate(1, 24, n)
rows["mixture+aug (median)"] = pd.DataFrame([facts(x) for x in R]).median().to_dict()
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(pd.DataFrame(rows).T.round(3))
