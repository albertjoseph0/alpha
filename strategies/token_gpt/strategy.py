"""Token GPT: the market as a language, decoded into positions.

See README.md. Model/tokenizer in gpt_core.py (sibling module).
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import copy

import numpy as np
import pandas as pd
import torch

import gpt_core as G
from harness import MarketData, Strategy
from harness.data import ASSETS, INDUSTRIES

torch.set_num_threads(1)

H = 5              # days per token ("word")
L = 64             # context length in tokens (~15 months)
K = 16             # vocabulary size (equal-frequency bins)
N_SEEDS = 3        # ensemble members
STEPS_FIRST = 400  # from-scratch training steps (pre-1950 learning curve: val minimum ~400)
STEPS_WARM = 150   # warm-start steps at each later refit
T_XS = 1.0         # decoding temperature across industries (softmax of standardised E[z])
PHASES = H         # average the decoded distribution over the last H daily tokenisations


class TokenGPT(Strategy):
    name = "transformer:gpt_token_kelly"
    refit_every = 504

    def __init__(self):
        self.edges = None
        self.models = None
        self.cmean = None
        self.fits = 0

    # ------------------------------------------------------------------
    @staticmethod
    def _excess(data: MarketData) -> np.ndarray:
        r = np.log1p(data.returns.reindex(columns=ASSETS).to_numpy(dtype=np.float64))
        rf = np.log1p(data.rf.to_numpy(dtype=np.float64))
        return r - rf[:, None]

    def fit(self, data: MarketData) -> None:
        x = self._excess(data)
        if self.edges is None:  # vocabulary frozen at the first fit
            z_in, _, _ = G.make_z(x, H)
            zz = z_in[np.isfinite(z_in)]
            self.edges = np.quantile(zz, np.linspace(0, 1, K + 1)[1:-1])
        c = G.Corpus(x, 0, H, self.edges)
        # decoding table: mean and mean-square of the target z inside each bin
        zo, to = c.z_out, c.tok_out
        ok = to >= 0
        self.cmean = np.array([zo[ok & (to == k)].mean() for k in range(K)])
        self.c2 = np.array([(zo[ok & (to == k)] ** 2).mean() for k in range(K)])
        t_max = len(x) - H - 2
        seed0 = int(data.last_date.strftime("%Y%m%d"))
        assets = list(range(len(ASSETS)))
        if self.models is None:
            self.models = []
            for s in range(N_SEEDS):
                torch.manual_seed(s)
                m = G.TinyGPT(K, L, d=32, n_layer=2, n_head=2, d_ff=64, dropout=0.1)
                G.train(m, c, assets, t_max, STEPS_FIRST, seed=seed0 + s)
                self.models.append(m)
        else:
            for s, m in enumerate(self.models):
                G.train(m, c, assets, t_max, STEPS_WARM, seed=seed0 + s, lr=5e-4)
        # float64 copies for batch-invariant inference
        self.inf = [copy.deepcopy(m).double().eval() for m in self.models]
        self.fits += 1

    # ------------------------------------------------------------------
    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        need = G.VOL_WINDOW + H * (L + 1) + PHASES + 5
        cal = data.dates
        i_first = int(cal.get_indexer([dates[0]])[0])
        lo = max(0, i_first - need)
        sub = MarketData(data.returns.iloc[lo:], data.rf.iloc[lo:])
        x = self._excess(sub)
        c = G.Corpus(x, 0, H, self.edges)
        pos = sub.dates.get_indexer(dates)
        A = len(ASSETS)
        # all end days needed: each date plus its PHASES-1 predecessors
        ends = np.unique(np.concatenate([pos - j for j in range(PHASES)]))
        ends = ends[ends >= H * (L - 1) + G.VOL_WINDOW + H]
        aa = np.repeat(np.arange(A), len(ends))
        tt = np.tile(ends, A)
        xin, _ = c.windows(aa, tt, L)
        valid = (xin >= 0).all(axis=(1, 2))
        xin = np.where(xin < 0, 0, xin)
        p = G.predict_probs(self.inf, xin)                     # (A*n, K)
        ez = p @ self.cmean
        ez2 = p @ self.c2
        ez[~valid] = np.nan
        EZ = pd.DataFrame(ez.reshape(A, len(ends)).T, index=ends)
        VZ = pd.DataFrame((ez2 - ez ** 2).reshape(A, len(ends)).T, index=ends)
        out = np.full((len(dates), A), np.nan)
        for r, t in enumerate(pos):
            win = [t - j for j in range(PHASES)]
            if not all(w in EZ.index for w in win):
                continue
            ez_t = EZ.loc[win].to_numpy().mean(axis=0)
            vz_t = VZ.loc[win].to_numpy().mean(axis=0)
            if not np.isfinite(ez_t).all():
                continue
            # 1) how much risk: Kelly fraction for the market from its predictive distribution
            sig = c.vol[t, 0] * np.sqrt(H)
            mu = ez_t[0] * sig
            var = max(vz_t[0], 1e-6) * sig * sig
            f = float(np.clip(mu / var, 0.0, 1.0))
            # 2) where: temperature softmax over industries of standardised E[z]
            s = ez_t[1:]
            s = (s - s.mean()) / (s.std() + 1e-12)
            w = np.exp(s / T_XS)
            w = w / w.sum()
            out[r, 1:] = f * w
            out[r, 0] = 0.0
        return pd.DataFrame(out, index=dates, columns=ASSETS)
