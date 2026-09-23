"""Evaluates the pre-declared configurations on etf_dev / etf_dev_a / etf_dev_b and appends each
to evals.log (one line per configuration). A configuration already in the log is not re-run.

    cd /home/user/alpha && PYTHONPATH=. .venv/bin/python strategies/r3_options/research.py [names...]
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import json
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import MarketData, Strategy
from strategy import SmoothMomentum

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evals.log")
OPT = ("PBP", "XYLD", "QYLD", "JEPI")
DEF = OPT + ("USMV", "VIXY")
T4 = (0, 5, 10, 15)


class CCSwitch(Strategy):
    """Hold the underlying, or its covered-call fund by regime (once the fund is listed).
    'always': always the covered call; 'trend': covered call when the underlying's 210-day
    return < 0; 'vol': covered call when 21-day realised vol > its expanding median."""
    refit_every = None

    def __init__(self, cc, under, mode, name):
        self.cc, self.under, self.mode, self.name = cc, under, mode, name

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.returns
        u = R[self.under].fillna(0.0)
        lp = np.log1p(u).cumsum()
        if self.mode == "trend":
            use = (lp - lp.shift(210)) < 0
        elif self.mode == "vol":
            rv = u.rolling(21).std()
            use = rv > rv.expanding(252).median()
        else:
            use = pd.Series(True, index=R.index)
        use = (use & (R[self.cc].notna().rolling(5).sum() == 5)).loc[dates].values
        out = pd.DataFrame(0.0, index=dates, columns=R.columns)
        out.loc[use, self.cc] = 1.0
        out.loc[~use, self.under] = 1.0
        return out


class Combo(Strategy):
    """Two SmoothMomentum sleeves with the same tranche days.
    mode 'blend' : w = a*on + (1-a)*off
    mode 'switch': on-sleeve when trend_asset's trend_len-day return > 0, else off-sleeve (whole book,
                   evaluated on each refresh day)."""
    refit_every = None

    def __init__(self, on, off, mode, name, a=0.5, trend_asset="SPY", trend_len=210):
        self.on, self.off, self.mode, self.name = on, off, mode, name
        self.a, self.trend_asset, self.trend_len = a, trend_asset, trend_len

    def predict(self, data, dates):
        w1 = self.on.predict(data, dates)
        w2 = self.off.predict(data, dates) if self.off is not None else w1 * 0.0
        if self.mode == "blend":
            return self.a * w1 + (1 - self.a) * w2
        lp = np.log1p(data.returns[self.trend_asset].fillna(0.0)).cumsum()
        up = ((lp - lp.shift(self.trend_len)) > 0).loc[dates].values
        out = w2.copy()
        out.loc[up] = w1.loc[up]
        return out


def configs():
    S = SmoothMomentum
    return {
        # --- covered call vs underlying (single asset) ---
        "cc_always_PBP": lambda: CCSwitch("PBP", "SPY", "always", "r3:options_cc_always_PBP"),
        "cc_trend_PBP": lambda: CCSwitch("PBP", "SPY", "trend", "r3:options_cc_trend_PBP"),
        "cc_vol_PBP": lambda: CCSwitch("PBP", "SPY", "vol", "r3:options_cc_vol_PBP"),
        # --- momentum core, option / defensive funds as candidates ---
        "mom5_1tr_all": lambda: S("mom", 5, "eq", (0,), (), "r3:options_mom5_1tr_all"),
        "mom5_1tr_noDEF": lambda: S("mom", 5, "eq", (0,), DEF, "r3:options_mom5_1tr_noDEF"),
        "sharpe7_4tr": lambda: S("sharpe", 7, "eq", (0, 5, 10, 15), ("VIXY",), "r3:options_sharpe7_4tr"),
        "sharpe7_4tr_noDEF": lambda: S("sharpe", 7, "eq", (0, 5, 10, 15), DEF, "r3:options_sharpe7_4tr_noDEF"),
        "sharpe7_4tr_withVIXY": lambda: S("sharpe", 7, "eq", (0, 5, 10, 15), (), "r3:options_sharpe7_4tr_withVIXY"),
        "sharpe5_4tr": lambda: S("sharpe", 5, "eq", (0, 5, 10, 15), ("VIXY",), "r3:options_sharpe5_4tr"),
        "sharpe10_4tr": lambda: S("sharpe", 10, "eq", (0, 5, 10, 15), ("VIXY",), "r3:options_sharpe10_4tr"),
        "sharpe7_4tr_invvol": lambda: S("sharpe", 7, "invvol", (0, 5, 10, 15), ("VIXY",), "r3:options_sharpe7_4tr_invvol"),
        "mom7_4tr": lambda: S("mom", 7, "eq", (0, 5, 10, 15), ("VIXY",), "r3:options_mom7_4tr"),
        # --- plain momentum (offense) combined with Sharpe momentum (defense) ---
        "blend50_mom5_sharpe7": lambda: Combo(S("mom", 5, "eq", T4, ("VIXY",)), S(), "blend",
                                              "r3:options_blend50_mom5_sharpe7"),
        "switch210_mom5_sharpe7": lambda: Combo(S("mom", 5, "eq", T4, ("VIXY",)), S(), "switch",
                                                "r3:options_switch210_mom5_sharpe7"),
        # sensitivity / ablations of the switch (declared before running)
        "switch126_mom5_sharpe7": lambda: Combo(S("mom", 5, "eq", T4, ("VIXY",)), S(), "switch",
                                                "r3:options_switch126_mom5_sharpe7", trend_len=126),
        "switch252_mom5_sharpe7": lambda: Combo(S("mom", 5, "eq", T4, ("VIXY",)), S(), "switch",
                                                "r3:options_switch252_mom5_sharpe7", trend_len=252),
        "switch210_mom7_sharpe7": lambda: Combo(S("mom", 7, "eq", T4, ("VIXY",)), S(), "switch",
                                                "r3:options_switch210_mom7_sharpe7"),
        "switch210_noDEF": lambda: Combo(S("mom", 5, "eq", T4, DEF), S(exclude=DEF), "switch",
                                         "r3:options_switch210_noDEF"),
        "switch210_mom5_cash": lambda: Combo(S("mom", 5, "eq", T4, ("VIXY",)), None, "switch",
                                             "r3:options_switch210_mom5_cash"),
    }


def _one(args):
    name, win = args
    data = harness.load_etf_dev()
    r = harness.run(configs()[name](), window=win, data=data, ledger=False)
    return name, win, r.cagr


def main(names):
    done = set()
    if os.path.exists(LOG):
        done = {json.loads(l)["config"] for l in open(LOG) if l.strip()}
    todo = [n for n in names if n not in done]
    wins = ("etf_dev", "etf_dev_a", "etf_dev_b")
    with Pool(4) as p:
        res = p.map(_one, [(n, w) for n in todo for w in wins])
    by = {}
    for n, w, c in res:
        by.setdefault(n, {})[w] = round(c * 100, 2)
    with open(LOG, "a") as f:
        for n in todo:
            k = len(done) + todo.index(n) + 1
            f.write(json.dumps({"n": k, "config": n, **by[n]}) + "\n")
            print(k, n, by[n])


if __name__ == "__main__":
    main(sys.argv[1:] or list(configs()))
