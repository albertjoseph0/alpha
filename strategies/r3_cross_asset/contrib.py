"""Per-group return contribution by year for a logged config (diagnostic)."""
import os, sys
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd, harness
from xasset import XAsset, GROUP, _meta
data = harness.load_etf_dev(); cal = data.dates
tag, kw = sys.argv[1].split("=", 1); kw = eval(f"dict({kw})")
dec = XAsset(**kw).predict(data, cal[cal >= "1999-12-01"]).ffill().reindex(cal).ffill().shift(2)
R = data.returns.fillna(0.0)
m = _meta(); g = pd.Series({c: GROUP[m.loc[c, "asset_class"]] for c in R.columns})
names = [c for c in R.columns if c in (sys.argv[2:] or [])]
C = (dec * R).loc["2000":]
out = C.T.groupby(g).sum().T.resample("YE").sum()
for c in names: out[c] = C[c].resample("YE").sum()
W = dec.loc["2000":].T.groupby(g).sum().T.resample("YE").mean()
print((out * 100).round(1).to_string()); print((W).round(2).to_string())
