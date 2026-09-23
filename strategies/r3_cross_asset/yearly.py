"""Yearly returns of already-logged configs (diagnostic, not a new config)."""
import os, sys
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd, harness
from harness.engine import simulate
from xasset import XAsset
data = harness.load_etf_dev(); cal = data.dates
cols = {}
for arg in sys.argv[1:]:
    tag, kw = arg.split("=", 1); kw = eval(f"dict({kw})")
    dec = XAsset(**kw).predict(data, cal[cal >= "1999-12-01"])
    eq = simulate(dec, data, pd.Timestamp("2000-01-01"), pd.Timestamp("2015-12-31")).equity
    ye = eq.resample("YE").last(); cols[tag] = ye.pct_change().fillna(ye.iloc[0] - 1)
spy = (1 + data.returns["SPY"].fillna(0)).loc["2000":].cumprod().resample("YE").last()
cols["SPY"] = spy.pct_change().fillna(spy.iloc[0] - 1)
print(pd.DataFrame(cols).round(3).to_string())
