"""Fractal-pretrained transformer volatility forecaster -> capped Kelly market exposure.

1. Pretrain (first fit() call, cached in memory) a small transformer on synthetic
   multifractal markets (ft_sim: MRW + leverage, multi-timescale ARCH with g1 < 0, MMAR
   cascade), generic literature parameters and a fixed seed; no real data involved.
2. Fine-tune walk-forward on the real history up to each refit date (Mkt + 12 industries
   as 13 univariate series; warm start from the previous refit).
3. Trade the market: w = min(1, mu / sigma2_21), the Kelly fraction with sigma2_21 the
   forecast variance over the next 21 trading days (starting t+2, matching the execution
   lag) and mu the long-run arithmetic excess return of Mkt over T-bills estimated from all
   data up to the refit date.  Direction is not forecast (Mandelbrot heresy 9).

Run:  .venv/bin/python -m harness strategies/fractal_transformer/strategy.py
"""
from __future__ import annotations

import copy
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import torch

import ft_model as fm
import ft_sim
from harness import ASSETS, MarketData, Strategy

torch.set_num_threads(1)

SYN_SEED, SYN_PATHS, SYN_LEN = 20240501, 384, 4000
PRE_STEPS, PRE_LR = 1500, 1e-3
FT0_STEPS, FT_STEPS, FT_LR = 300, 120, 3e-4
H_TRADE = 1                     # index of the 21-day horizon in fm.HORIZONS

_PRETRAINED: dict = {}          # in-memory cache of pretrained weights (per process)


def pretrained_state(seed: int = SYN_SEED) -> dict:
    if seed not in _PRETRAINED:
        R = ft_sim.generate(seed, SYN_PATHS, SYN_LEN)
        C = fm.Corpus(R)
        tt = np.arange(1000, C.N - 2 - max(fm.HORIZONS))
        ip = np.repeat(np.arange(R.shape[0]), len(tt)); it = np.tile(tt, R.shape[0])
        torch.manual_seed(seed)
        m = fm.VolTransformer()
        fm.train(m, C, ip, it, PRE_STEPS, PRE_LR, seed)
        _PRETRAINED[seed] = copy.deepcopy(m.state_dict())
    return _PRETRAINED[seed]


class FractalTransformer(Strategy):
    name = "hybrid:fractal_transformer_kelly"
    refit_every = 504

    def __init__(self, pretrain: bool = True, finetune: bool = True, init_seed: int = 7):
        self.pretrain, self.finetune, self.init_seed = pretrain, finetune, init_seed
        self.model = None
        self.model64 = None
        self.mu = 0.06

    def fit(self, data: MarketData) -> None:
        first = self.model is None
        if first:
            torch.manual_seed(self.init_seed)
            self.model = fm.VolTransformer()
            if self.pretrain:
                self.model.load_state_dict(pretrained_state())
        if self.finetune:
            lr = data.log_returns()[ASSETS].to_numpy().T              # (13, N)
            C = fm.Corpus(lr)
            tt = np.arange(fm.MIN_T, C.N - 2 - max(fm.HORIZONS))
            ip = np.repeat(np.arange(lr.shape[0]), len(tt)); it = np.tile(tt, lr.shape[0])
            seed = int(data.last_date.strftime("%Y%m%d"))
            fm.train(self.model, C, ip, it, FT0_STEPS if first else FT_STEPS, FT_LR, seed)
        self.model64 = copy.deepcopy(self.model).double().eval()
        ex = (data.returns["Mkt"] - data.rf).to_numpy()
        self.mu = float(max(ex.mean() * 252.0, 0.0))

    def forecast_var(self, data: MarketData, dates: pd.DatetimeIndex) -> np.ndarray:
        """Annualized forecast variances (len(dates), len(HORIZONS))."""
        C = fm.Corpus(data.log_returns()["Mkt"].to_numpy()[None, :])
        t = data.dates.get_indexer(dates)
        lv = fm.predict_logvar(self.model64, C, np.zeros(len(t), dtype=int), t)
        return np.exp(lv) * 252.0

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        var = self.forecast_var(data, dates)[:, H_TRADE]
        w = np.minimum(1.0, self.mu / var)
        return pd.DataFrame({"Mkt": w}, index=dates)
