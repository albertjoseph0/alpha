import os; os.environ["OMP_NUM_THREADS"]="1"
import sys; sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, "/home/user/alpha/strategies/_example_etf")
import numpy as np, pandas as pd, harness
from harness.engine import simulate
from strategy import ETFMomentumTemplate
data = harness.load_etf_dev(); meta = harness.etf_meta().set_index("ticker") if "ticker" in harness.etf_meta().columns else harness.etf_meta()
s = ETFMomentumTemplate(); cal = data.dates
dec = s.predict(data, cal[cal >= "1999-12-01"])
sim = simulate(dec, data, pd.Timestamp("2000-01-01"), pd.Timestamp("2015-12-31"))
eq = sim.equity; yr = eq.resample("YE").last().pct_change(); yr.iloc[0] = eq.resample("YE").last().iloc[0]/1-1
spy = (1+data.returns["SPY"].fillna(0)).cumprod(); spyr = spy.resample("YE").last().pct_change()
print(pd.DataFrame({"base": yr, "SPY": spyr}).loc["2000":].round(3).to_string())
W = dec.dropna(how="all"); W = W.loc["2007-12":]
cls = meta["asset_class"]
bycls = W.T.groupby(cls).sum().T
print(bycls.resample("YE").mean().round(2).to_string())
top = W.resample("YE").mean().T
for y in top.columns: print(y.year, top[y].nlargest(6).round(2).to_dict())
