import os, sys
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd, harness
from harness.engine import simulate
from xasset import XAsset
data = harness.load_etf_dev(); cal = data.dates
tag, kw = sys.argv[1].split("=", 1); kw = eval(f"dict({kw})")
a, b = sys.argv[2], sys.argv[3]
dec = XAsset(**kw).predict(data, cal[cal >= "1999-12-01"])
eq = simulate(dec, data, pd.Timestamp("2000-01-01"), pd.Timestamp("2015-12-31")).equity
mr = eq.resample("ME").last().pct_change().loc[a:b]
W = dec.dropna(how="all").ffill().resample("ME").last().loc[a:b]
for d in mr.index:
    w = W.loc[d]; w = w[w > 0.01].sort_values(ascending=False).round(2)
    print(d.strftime("%Y-%m"), f"{mr.loc[d]:+.3f}", dict(w))
