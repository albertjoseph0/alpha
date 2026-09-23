"""Scale-free multi-scale features, a small transformer volatility forecaster, and training.

Features for a window ending at day t (L daily "tokens"), all divided by the reference
variance s2 = EWMA_50(r^2)[t] so the model never sees the volatility *level* (this is what
makes pretraining on synthetic markets of arbitrary scale transferable):
  z      r_i / s                       normalized daily return (sign -> leverage effect)
  la     log(r_i^2 / s2 + 0.05)        log amplitude (MRW log-vol proxy, Borland eq. 12)
  lv_h   log(EWMA_h(r^2)_i / s2)       h = 2,10,50,250,1000 days: the multi-scale cascade
                                       (long-horizon vol drives short-horizon vol, p. 12)
  m_k    (x_i - x_{i-k}) / sqrt(k s2)  k = 21,126: the r~_{i,k} of Borland eq. 15
Targets: y_h = log(mean_{j=t+2}^{t+1+h} r_j^2 / s2) for h = 5, 21, 63 (starts at t+2 because
of the harness's 1-day execution lag), fitted with the QLIKE loss exp(y - yhat) + yhat,
whose minimizer is log E[RV/s2] (an unbiased variance forecast, what a Kelly rule needs).
All features are causal IIR filters (scipy lfilter), so values at day t are bitwise
identical whatever data follows t (batch invariance for the harness's causality audit).
"""
from __future__ import annotations

import numpy as np
import torch
from scipy.signal import lfilter
from torch import nn

HALFLIVES = (2, 10, 50, 250, 1000)
REF = 2                       # index of the 50-day EWMA in HALFLIVES
HORIZONS = (5, 21, 63)
MOM = (21, 126)
L = 64
N_FEAT = 2 + len(HALFLIVES) + len(MOM)
MIN_T = 260                   # first usable window end (needs x_{t-126-L})


class Corpus:
    """Precomputed per-day quantities for P aligned series of length N (rows = series)."""

    def __init__(self, r: np.ndarray):
        r = np.atleast_2d(np.asarray(r, dtype=np.float64))
        self.r = r
        P, N = r.shape
        r2 = r * r
        self.logv = np.empty((len(HALFLIVES), P, N))
        for j, h in enumerate(HALFLIVES):
            a = 1.0 - 0.5 ** (1.0 / h)
            num = lfilter([1.0], [1.0, -(1.0 - a)], r2, axis=1)
            den = lfilter([1.0], [1.0, -(1.0 - a)], np.ones_like(r2), axis=1)
            self.logv[j] = np.log(num / den + 1e-12)
        self.x = np.concatenate([np.zeros((P, 1)), np.cumsum(r, axis=1)], axis=1)  # x[:, i+1] = price after day i
        self.cs = np.concatenate([np.zeros((P, 1)), np.cumsum(r2, axis=1)], axis=1)
        self.N = N

    def windows(self, p: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Inputs (B, L, N_FEAT) for series p ending at day t (float64)."""
        pos = t[:, None] + np.arange(-L + 1, 1)[None, :]            # (B, L)
        pp = p[:, None]
        ls2 = self.logv[REF][p, t][:, None]                           # (B, 1)
        s = np.exp(0.5 * ls2)
        r = self.r[pp, pos]
        feats = [np.clip(r / s, -10, 10), np.log(r * r / np.exp(ls2) + 0.05)]
        for j in range(len(HALFLIVES)):
            feats.append(self.logv[j][pp, pos] - ls2)
        xi = self.x[pp, pos + 1]
        for k in MOM:
            feats.append(np.clip((xi - self.x[pp, pos + 1 - k]) / (np.sqrt(k) * s), -10, 10))
        return np.stack(feats, axis=-1)

    def targets(self, p: np.ndarray, t: np.ndarray) -> np.ndarray:
        ls2 = self.logv[REF][p, t]
        out = []
        for h in HORIZONS:
            rv = (self.cs[p, t + 2 + h] - self.cs[p, t + 2]) / h
            out.append(np.log(rv / np.exp(ls2) + 1e-4))
        return np.stack(out, axis=-1)

    def ref_var(self, p, t):
        return np.exp(self.logv[REF][p, t])


class VolTransformer(nn.Module):
    def __init__(self, d=32, heads=4, layers=2, ff=64):
        super().__init__()
        self.inp = nn.Linear(N_FEAT, d)
        self.pos = nn.Parameter(torch.zeros(1, L, d))
        layer = nn.TransformerEncoderLayer(d, heads, ff, dropout=0.0, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d)
        self.head = nn.Linear(d, len(HORIZONS))
        nn.init.normal_(self.pos, std=0.02)
        nn.init.zeros_(self.head.weight); nn.init.zeros_(self.head.bias)

    def forward(self, x):
        h = self.enc(self.inp(x) + self.pos)
        return self.head(self.norm(h[:, -1]))        # read out at the last ("next-token") position


def qlike(yhat, y):
    return (torch.exp(y - yhat) + yhat - y - 1.0).mean()


def train(model, corpus: Corpus, idx_p: np.ndarray, idx_t: np.ndarray, steps: int, lr: float,
          seed: int, batch: int = 256) -> float:
    """AdamW on uniformly sampled (series, day) pairs; returns mean loss of last 20% steps."""
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    model.train()
    losses = []
    for _ in range(steps):
        k = rng.integers(0, len(idx_p), batch)
        p, t = idx_p[k], idx_t[k]
        xb = torch.from_numpy(corpus.windows(p, t).astype(np.float32))
        yb = torch.from_numpy(corpus.targets(p, t).astype(np.float32))
        loss = qlike(model(xb), yb)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
        losses.append(loss.item())
    model.eval()
    return float(np.mean(losses[-max(1, steps // 5):]))


@torch.no_grad()
def predict_logvar(model64, corpus: Corpus, p: np.ndarray, t: np.ndarray) -> np.ndarray:
    """log of forecast daily variance (B, len(HORIZONS)), float64 inference."""
    x = torch.from_numpy(corpus.windows(p, t))
    yhat = model64(x).numpy()
    return yhat + corpus.logv[REF][p, t][:, None]
