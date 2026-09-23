"""deep:trend_switch_ens -- robust version of the round-3 winner (r3:options_switch210_mom5_sharpe7).

Developed by the orchestrator (no subagents) on ETF 2000-2015 + an independent 1965-1999 proxy
history (research/deep/). Frozen before its single 2016+ holdout run.

  * Regime: fraction of four SPY trend signals that are up, over 126, 168, 210 and 252 trading days
    (6, 8, 10 and 12 months). Averaging replaces the single, luckiest 210-day choice.
  * Offense (weight = regime): 12-1 month momentum across the ETF universe, top 5, equal weight.
  * Defense (weight = 1 - regime): 12-1 month return / 12-month vol, top 7, equal weight
    (in practice Treasuries, TIPS, gold and defensive sectors).
  * Both sleeves: 4 staggered monthly tranches (trading days 0/5/10/15); VIXY excluded.
Long only, fully invested, no leverage.

Run:  .venv/bin/python -m harness strategies/deep_trend_switch/strategy.py --window etf_dev --benchmarks
Live: .venv/bin/python -m harness.live strategies/deep_trend_switch/strategy.py --capital 100000 --refresh
"""
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "r3_options"))
from harness import MarketData, Strategy
from strategy import MomentumSleeve  # r3_options sleeve (unchanged)

TREND_LENGTHS = (126, 168, 210, 252)


class DeepTrendSwitchEnsemble(Strategy):
    name = "deep:trend_switch_ens"
    refit_every = None

    def __init__(self):
        self.offense = MomentumSleeve("mom", 5, "eq", (0, 5, 10, 15), ("VIXY",))
        self.defense = MomentumSleeve("sharpe", 7, "eq", (0, 5, 10, 15), ("VIXY",))

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        w_on = self.offense.predict(data, dates)
        w_off = self.defense.predict(data, dates)
        lp = np.log1p(data.returns["SPY"].fillna(0.0)).cumsum()
        up = sum(((lp - lp.shift(L)) > 0).astype(float) for L in TREND_LENGTHS) / len(TREND_LENGTHS)
        up = up.reindex(dates).to_numpy()
        return w_on.mul(up, axis=0) + w_off.mul(1.0 - up, axis=0)
