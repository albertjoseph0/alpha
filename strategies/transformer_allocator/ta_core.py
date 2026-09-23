"""Core of the end-to-end transformer allocator.

Pieces
------
* ``features``   : batch-invariant (float64, cumulative-sum) multi-horizon tokens per asset.
* ``rebalance_mask``: weekly decision schedule (first trading day of each ISO week).
* ``build_samples``: decision dates + holding-period gross returns (1-day execution lag).
* ``Allocator``  : a small transformer over (time-block x asset) tokens + one CLS token per
                   asset + one cash token; softmax over the 13 assets and cash gives
                   long-only weights with sum(w) = 1 (so sum|w| <= 1 holds by construction).
* ``train_member`` / ``fit_ensemble``: maximise mean log growth of the weekly-rebalanced
                   portfolio net of 5 bp turnover costs, AdamW + dropout + early stopping on a
                   time-ordered validation fold, several members averaged.

Everything that the harness scores goes through ``ensemble_weights`` in float64, so the
causality audit (tolerance 1e-5) sees identical numbers whatever the batch.
"""
from __future__ import annotations

import copy
import math
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import torch
import torch.nn as nn

torch.set_num_threads(1)

COST = 0.0005          # harness: 5 bp per unit of one-way turnover
EXEC_LAG = 1           # harness: decide at close t, trade at close t+1, earn from t+2

# Time blocks, in trading days back from the decision date (lag 1 = the decision day itself).
# Roughly dyadic, like the multi-timescale kernel K(k) of Borland et al. (p. 14):
# 1 week, rest of month, months 2-3, months 4-6, months 7-12, year 2.
BLOCKS = ((1, 5), (6, 21), (22, 63), (64, 126), (127, 252), (253, 504))
LOOKBACK = max(e for _, e in BLOCKS)          # 504 rows needed for a complete token set
VOL_WIN = 252                                  # long-run vol used to normalise returns
N_FEAT = 3                                     # per token: z-return, log-vol, long-run log-vol


def _soft_clip(x: np.ndarray, c: float) -> np.ndarray:
    return c * np.tanh(x / c)


def features(R: np.ndarray) -> np.ndarray:
    """Token features for every row of simple returns ``R`` (n x A).

    Returns ``F`` of shape (n, A, J, N_FEAT); rows before LOOKBACK-1 are NaN.
    Row i uses only R[:i+1]. Pure cumulative sums in float64 -> batch invariant.
    """
    x = np.log1p(np.asarray(R, dtype=np.float64))
    n, A = x.shape
    z = np.zeros((1, A))
    C1 = np.vstack([z, np.cumsum(x, axis=0)])
    C2 = np.vstack([z, np.cumsum(x * x, axis=0)])
    F = np.full((n, A, len(BLOCKS), N_FEAT), np.nan)
    idx = np.arange(n)
    ok = idx >= LOOKBACK - 1
    i = idx[ok]
    # long-run vol (RMS of daily log returns over VOL_WIN days)
    s2L = (C2[i + 1] - C2[i + 1 - VOL_WIN]) / VOL_WIN
    sL = np.sqrt(np.maximum(s2L, 1e-10))
    logvL = np.log(sL * math.sqrt(252) / 0.16)
    for j, (s, e) in enumerate(BLOCKS):
        a, b = i - e + 1, i - s + 1          # rows a..b inclusive
        L = e - s + 1
        s1 = C1[b + 1] - C1[a]
        s2 = C2[b + 1] - C2[a]
        zret = s1 / (sL * math.sqrt(L))
        logv = 0.5 * np.log(np.maximum(s2 / L, 1e-10) * 252) - math.log(0.16)
        F[ok, :, j, 0] = _soft_clip(zret, 4.0)
        F[ok, :, j, 1] = _soft_clip(logv, 3.0)
        F[ok, :, j, 2] = _soft_clip(logvL, 3.0)
    return F


def rebalance_mask(dates) -> np.ndarray:
    """True on the first trading day of each ISO week (depends only on the previous date)."""
    iso = dates.isocalendar()
    key = (iso["year"].to_numpy() * 100 + iso["week"].to_numpy()).astype(np.int64)
    m = np.ones(len(dates), dtype=bool)
    m[1:] = key[1:] != key[:-1]
    return m


def build_samples(R: np.ndarray, rf: np.ndarray, reb: np.ndarray, last_row: int):
    """Decision rows and their holding-period gross growth, using rows <= last_row only.

    Decision at row t trades at close t+1 and holds from row t+2 through row t'+1, where t'
    is the next decision row. Returns (rows, G_assets (m x A), G_cash (m,)).
    """
    dec = np.flatnonzero(reb[: last_row + 1])
    dec = dec[dec >= LOOKBACK - 1]
    rows, GA, GC = [], [], []
    lr = np.log1p(R)
    lrf = np.log1p(rf)
    C = np.vstack([np.zeros((1, R.shape[1])), np.cumsum(lr, axis=0)])
    Cf = np.concatenate([[0.0], np.cumsum(lrf)])
    for k in range(len(dec) - 1):
        t, t2 = dec[k], dec[k + 1]
        a, b = t + 1 + EXEC_LAG, t2 + EXEC_LAG        # holding rows a..b inclusive
        if b > last_row:
            break
        rows.append(t)
        GA.append(np.exp(C[b + 1] - C[a]))
        GC.append(math.exp(Cf[b + 1] - Cf[a]))
    return np.array(rows, dtype=np.int64), np.array(GA), np.array(GC)


# ----------------------------------------------------------------------------------- model
class Block(nn.Module):
    """Pre-LayerNorm transformer block: multi-head self-attention + feed-forward."""

    def __init__(self, d: int, heads: int, ff: int, drop: float):
        super().__init__()
        self.h = heads
        self.ln1 = nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d)
        self.proj = nn.Linear(d, d)
        self.ln2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.GELU(), nn.Linear(ff, d))
        self.drop = nn.Dropout(drop)

    def forward(self, x):
        B, N, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).view(B, N, 3, self.h, d // self.h).permute(2, 0, 3, 1, 4)
        att = torch.softmax(q @ k.transpose(-1, -2) / math.sqrt(d // self.h), dim=-1)
        a = (att @ v).transpose(1, 2).reshape(B, N, d)
        x = x + self.drop(self.proj(a))
        return x + self.drop(self.ff(self.ln2(x)))


class Allocator(nn.Module):
    """Factorised (time x asset) transformer -> long-only weights over 13 assets + cash.

    Embedding (Wolfram p. 64-65): token = Linear(features) + time-block (positional)
    embedding + asset-type embedding (market vs industry; optional per-asset ids).
    Attention, repeated ``layers`` times (divided / axial attention):
      1. temporal: each asset's CLS ("now") token and its J time-block tokens attend to each
         other (the learned analogue of the multi-timescale kernel K(k), Borland et al. p. 14);
      2. cross-asset: the 13 CLS tokens and one cash token attend to each other.
    Decoding (Wolfram p. 69-70): a shared linear head reads a score from every CLS token, a
    separate head reads the cash score, and a softmax over the 14 scores gives the weights.
    Without per-asset ids the model is permutation-equivariant across industries, so it cannot
    memorise which industry won in-sample; it can only learn rules on the features.
    """

    def __init__(self, n_assets=13, n_blocks=len(BLOCKS), n_feat=N_FEAT, d=16, heads=2,
                 layers=1, ff=32, drop=0.1, asset_ids=False, cash_bias=-2.5):
        super().__init__()
        self.A, self.J = n_assets, n_blocks
        self.inp = nn.Linear(n_feat, d)
        self.pos = nn.Parameter(torch.randn(n_blocks + 1, d) * 0.1)   # index J: CLS position
        n_types = n_assets if asset_ids else 2                        # 2 = market / industry
        self.typ = nn.Parameter(torch.randn(n_types, d) * 0.1)
        self.cash = nn.Parameter(torch.randn(1, d) * 0.1)
        self.tblocks = nn.ModuleList([Block(d, heads, ff, drop) for _ in range(layers)])
        self.ablocks = nn.ModuleList([Block(d, heads, ff, drop) for _ in range(layers)])
        self.lnf = nn.LayerNorm(d)
        self.head = nn.Linear(d, 1)
        self.head_cash = nn.Linear(d, 1)
        nn.init.zeros_(self.head.weight); nn.init.zeros_(self.head.bias)
        nn.init.zeros_(self.head_cash.weight); nn.init.constant_(self.head_cash.bias, cash_bias)
        tidx = torch.arange(n_assets) if asset_ids else torch.tensor([0] + [1] * (n_assets - 1))
        self.register_buffer("tidx", tidx)

    def forward(self, X):
        """X: (B, A, J, F) -> weights (B, A+1); last column is cash."""
        B, A, J, _ = X.shape
        d = self.pos.shape[1]
        typ = self.typ[self.tidx]                                        # (A, d)
        tok = self.inp(X) + self.pos[:J].view(1, 1, J, d) + typ.view(1, A, 1, d)
        cls = (self.pos[J].view(1, 1, 1, d) + typ.view(1, A, 1, d)).expand(B, A, 1, d)
        h = torch.cat([cls, tok], dim=2)                                 # (B, A, J+1, d)
        c = self.cash.view(1, 1, d).expand(B, 1, d)
        for tb, ab in zip(self.tblocks, self.ablocks):
            h = tb(h.reshape(B * A, J + 1, d)).view(B, A, J + 1, d)      # temporal attention
            z = ab(torch.cat([h[:, :, 0], c], dim=1))                    # cross-asset attention
            h = torch.cat([z[:, :A].unsqueeze(2), h[:, :, 1:]], dim=2)
            c = z[:, A:]
        s_a = self.head(self.lnf(h[:, :, 0])).squeeze(-1)                # (B, A)
        s_c = self.head_cash(self.lnf(c[:, 0]))                          # (B, 1)
        return torch.softmax(torch.cat([s_a, s_c], dim=1), dim=1)


# -------------------------------------------------------------------------------- training
def chunk_loss(W, GA, GC, cost=COST):
    """Negative mean log growth of consecutive weekly holding periods, net of costs.

    W: (k, L, A+1) weights for k chunks of L consecutive decisions; GA: (k, L, A) and
    GC: (k, L) gross growth over each holding period. Turnover is measured against the
    previous period's drifted weights, exactly as the harness engine does.
    """
    G = torch.cat([GA, GC.unsqueeze(-1)], dim=-1)
    P = (W * G).sum(-1)                                                # (k, L)
    drift = W[:, :-1] * G[:, :-1] / P[:, :-1].unsqueeze(-1)
    to = (W[:, 1:, :-1] - drift[:, :, :-1]).abs().sum(-1)             # cash is not traded
    lg = torch.log(P)
    lg = torch.cat([lg[:, :1], lg[:, 1:] + torch.log1p(-cost * to)], dim=1)
    return -lg.mean()


def _forward_chunks(model, X, idx):
    k, L = idx.shape
    W = model(X[idx.reshape(-1)])
    return W.view(k, L, -1)


def _eval_logg(model, X, GA, GC):
    """Mean weekly log growth over one contiguous slice (eval mode, no dropout)."""
    model.eval()
    with torch.no_grad():
        idx = torch.arange(len(X)).view(1, -1)
        W = _forward_chunks(model, X, idx)
        return -chunk_loss(W, GA[idx], GC[idx]).item()


class LinearAllocator(nn.Module):
    """No-attention baseline ("perceptron", Wolfram p. 47): a linear read-out of the same
    multi-horizon tokens -- i.e. a learned multi-timescale kernel sum_k K(k) G(r_k) as in
    Borland et al. eq. (15) -- with the same softmax over assets + cash."""

    def __init__(self, n_assets=13, n_blocks=len(BLOCKS), n_feat=N_FEAT, cash_bias=-2.5, **_):
        super().__init__()
        m = n_blocks * n_feat
        self.lin = nn.Linear(m, 1)
        self.typ = nn.Parameter(torch.zeros(2))
        self.lin_cash = nn.Linear(m, 1)
        nn.init.zeros_(self.lin.weight); nn.init.zeros_(self.lin.bias)
        nn.init.zeros_(self.lin_cash.weight); nn.init.constant_(self.lin_cash.bias, cash_bias)
        self.register_buffer("tidx", torch.tensor([0] + [1] * (n_assets - 1)))

    def forward(self, X):
        B, A, J, Fd = X.shape
        f = X.reshape(B, A, J * Fd)
        s_a = self.lin(f).squeeze(-1) + self.typ[self.tidx]
        s_c = self.lin_cash(f.mean(1))
        return torch.softmax(torch.cat([s_a, s_c], dim=1), dim=1)


def make_model(cfg):
    kind = cfg.get("model", "transformer")
    if kind == "linear":
        return LinearAllocator()
    return Allocator(d=cfg["d"], heads=cfg["heads"], layers=cfg["layers"], ff=cfg["ff"],
                     drop=cfg["drop"], asset_ids=cfg.get("asset_ids", False))


def train_member(X, GA, GC, train_mask, val_slice, seed, cfg):
    """Train one member on shuffled contiguous chunks of ``chunk`` weeks drawn from the
    training part (``train_mask``); early-stop on the log growth of the contiguous
    validation slice ``val_slice`` (a time-ordered fold of the training data)."""
    torch.manual_seed(seed)
    g = np.random.default_rng(seed)
    model = make_model(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
    n, L, kb = len(X), cfg["chunk"], cfg["chunks_per_batch"]
    ok = np.concatenate([[0], np.cumsum(train_mask.astype(int))])
    valid = np.array([s for s in range(n - L + 1) if ok[s + L] - ok[s] == L], dtype=np.int64)
    has_val = val_slice is not None and (val_slice.stop - val_slice.start) > 10
    if has_val:
        Xv, GAv, GCv = X[val_slice], GA[val_slice], GC[val_slice]
        best = _eval_logg(model, Xv, GAv, GCv)
    best_state, best_ep, hist, bad = copy.deepcopy(model.state_dict()), 0, [], 0
    if has_val:
        hist.append(best)
    for ep in range(cfg["epochs"]):
        model.train()
        off = int(g.integers(0, L))
        starts = valid[(valid - off) % L == 0]
        g.shuffle(starts)
        for b0 in range(0, len(starts), kb):
            st = torch.from_numpy(starts[b0: b0 + kb])
            idx = st.view(-1, 1) + torch.arange(L).view(1, -1)
            opt.zero_grad()
            loss = chunk_loss(_forward_chunks(model, X, idx), GA[idx], GC[idx])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        if has_val:
            v = _eval_logg(model, Xv, GAv, GCv)
            hist.append(v)
            if v > best + 1e-7:
                best, best_state, best_ep, bad = v, copy.deepcopy(model.state_dict()), ep + 1, 0
            else:
                bad += 1
                if bad >= cfg["patience"]:
                    break
    if has_val:
        model.load_state_dict(best_state)
    else:
        best_ep = cfg["epochs"]
    model.eval()
    return model, best_ep, hist


def fit_ensemble(F, R, rf, reb, last_row, cfg, seed_base):
    """Blocked time-fold ensemble. The weekly samples available at ``last_row`` are split into
    K contiguous folds; member k early-stops on fold k and trains on the rest (with a small
    purge gap). Every sample is used for training by K-1 members, and each member's stopping
    point is judged on a different era. Returns (models, info)."""
    rows, GA, GC = build_samples(R, rf, reb, last_row)
    X = torch.tensor(F[rows], dtype=torch.float32)
    GA = torch.tensor(GA, dtype=torch.float32)
    GC = torch.tensor(GC, dtype=torch.float32)
    n, K, gap = len(rows), cfg["members"], cfg.get("purge", 2)
    edges = np.linspace(0, n, K + 1).astype(int)
    models, info = [], []
    for k in range(K):
        a, b = edges[k], edges[k + 1]
        mask = np.ones(n, dtype=bool)
        mask[max(0, a - gap): min(n, b + gap)] = False
        m, be, hist = train_member(X, GA, GC, mask, slice(a, b), seed_base * 16 + k, cfg)
        models.append(m)
        info.append({"fold": k, "best_ep": be, "val_hist": [round(h * 52, 4) for h in hist]})
    return models, info


def ensemble_weights(models, X: np.ndarray) -> np.ndarray:
    """Average member weights, computed in float64 (batch invariant)."""
    Xt = torch.from_numpy(np.ascontiguousarray(X, dtype=np.float64))
    out = np.zeros((len(X), X.shape[1] + 1))
    with torch.no_grad():
        for m in models:
            md = copy.deepcopy(m).double().eval()
            out += md(Xt).numpy()
    return out / len(models)
