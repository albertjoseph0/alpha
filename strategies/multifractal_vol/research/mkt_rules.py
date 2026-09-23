"""Market-only exposure rules driven by the walk-forward vol forecasts."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/user/alpha/strategies/multifractal_vol/research")
from bt import evaluate, DATA

SP = "/tmp/claude-0/-home-user-alpha/98ea3775-9ac1-5aa8-9c82-12ae31cc8668/scratchpad/"
sc = pd.read_pickle(SP + "fc_Mkt.pkl")
H = 21
ex = DATA.returns["Mkt"] - DATA.rf
# causal expanding mean excess return (annualised), from 1926
mu = ex.expanding(min_periods=500).mean() * 252

which = sys.argv[1:] or ["bh", "kelly"]
if "bh" in which:
    evaluate(pd.DataFrame({"Mkt": 1.0}, index=DATA.dates), "buy&hold (sanity)")
if "kelly" in which:
    for k in ["ewma", "garch", "har", "mrw", "mtarch"]:
        var_ann = sc[k] * 252 / H
        w = np.clip(mu / var_ann, 0, 1)
        evaluate(pd.DataFrame({"Mkt": w}), f"kelly mu=expanding {k}")
if "voltgt" in which:
    for k in ["ewma", "garch", "har", "mrw", "mtarch"]:
        vol = np.sqrt(sc[k] * 252 / H)
        tgt = vol.expanding(min_periods=252).median()
        w = np.clip(1.25 * tgt / vol, 0, 1)
        evaluate(pd.DataFrame({"Mkt": w}), f"voltgt 1.25x median {k}")
