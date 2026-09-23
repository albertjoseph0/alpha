"""Core of the r2 transformer cross-sectional ranker (49 industries, monthly).

* ``month_starts``  : decision rows = first trading day of each month (as the rule baseline).
* ``features``      : per-industry momentum-family features at given rows, float64 cumsums
                      from the start of the data -> batch-invariant (causality audit safe).
* ``rule_weights``  : plain 12-1 momentum, top third, equal weight (round-2 baseline).
* ``SetRanker``     : set-attention transformer over the valid industries (no identity
                      embeddings -> permutation-equivariant), score head, masked softmax.
* ``LinearRanker``  : same features, score = w.x, masked softmax (the linear control).
* ``fit_ensemble``  : K contiguous-fold members, each early-stopped on its held-out fold,
                      trained to maximise monthly log growth net of 5 bp turnover costs,
                      with the harness 1-day execution lag built into the labels.
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

COST = 0.0005
EXEC_LAG = 1
LOOK = 252
N_FEAT = 13


def month_starts(dates) -> np.ndarray:
    """True on the first trading day of each month (depends only on the previous date)."""
    m = np.ones(len(dates), dtype=bool)
    mo = dates.month.to_numpy()
    m[1:] = mo[1:] != mo[:-1]
    return m


def _sc(x, c):
    return c * np.tanh(x / c)


class Prep:
    """Cumulative sums of one MarketData snapshot (industries + market)."""

    def __init__(self, R_ind, r_mkt):
        R = np.asarray(R_ind, dtype=np.float64)
        self.valid_raw = ~np.isnan(R)
        x = np.log1p(np.nan_to_num(R, nan=0.0))
        z = np.zeros((1, R.shape[1]))
        self.C = np.vstack([z, np.cumsum(x, axis=0)])
        self.C2 = np.vstack([z, np.cumsum(x * x, axis=0)])
        self.CV = np.vstack([z, np.cumsum(self.valid_raw.astype(np.float64), axis=0)])
        xm = np.log1p(np.nan_to_num(np.asarray(r_mkt, dtype=np.float64), nan=0.0))
        self.Cm = np.concatenate([[0.0], np.cumsum(xm)])
        self.Cm2 = np.concatenate([[0.0], np.cumsum(xm * xm)])
        self.n = R.shape[0]

    def ret(self, i, L, skip=0):          # log return over rows i-L+1 .. i-skip
        return self.C[i + 1 - skip] - self.C[i + 1 - L]

    def valid(self, i):                   # >= 250 valid days in the last 252 (as the rule)
        if i < LOOK - 1:
            return np.zeros(self.C.shape[1], dtype=bool)
        return (self.CV[i + 1] - self.CV[i + 1 - LOOK]) >= 250


def features(P: Prep, rows) -> tuple[np.ndarray, np.ndarray]:
    """F (m, A, N_FEAT) and valid mask (m, A) at decision rows (each needs row >= 252)."""
    rows = np.asarray(rows, dtype=np.int64)
    A = P.C.shape[1]
    F = np.zeros((len(rows), A, N_FEAT))
    V = np.zeros((len(rows), A), dtype=bool)
    for q, i in enumerate(rows):
        if i < LOOK:
            continue
        v = P.valid(i)
        s2 = (P.C2[i + 1] - P.C2[i + 1 - LOOK]) / LOOK
        sig = np.sqrt(np.maximum(s2, 1e-10))
        s2s = (P.C2[i + 1] - P.C2[i + 1 - 63]) / 63
        f = []
        for L in (21, 63, 126, 189, 252):
            f.append(_sc(P.ret(i, L) / (sig * math.sqrt(L)), 4.0))
        m121 = P.ret(i, 252, skip=21)
        f.append(_sc(m121 / (sig * math.sqrt(231)), 4.0))                  # z 12-1
        f.append(_sc(m121 / 0.25, 4.0))                                   # raw 12-1
        # path smoothness: 12m log return / sum of |5-day log returns| over 50 blocks
        abs5 = np.zeros(A)
        for k in range(50):
            b = i + 1 - 5 * k
            abs5 += np.abs(P.C[b] - P.C[b - 5])
        f.append(P.ret(i, 250) / np.maximum(abs5, 1e-8))
        f.append(_sc(np.log(sig * math.sqrt(252) / 0.2), 3.0))            # log vol 1y
        f.append(_sc(0.5 * np.log(np.maximum(s2s, 1e-10) / np.maximum(s2, 1e-10)), 3.0))
        # cross-sectional rank of 12-1 among valid industries, in [-1, 1]
        rk = np.zeros(A)
        mv = m121[v]
        if v.sum() > 1:
            order = np.argsort(np.argsort(mv, kind="stable"), kind="stable")
            rk[v] = 2.0 * order / (v.sum() - 1) - 1.0
        f.append(rk)
        # market state (same for every industry)
        sm2 = (P.Cm2[i + 1] - P.Cm2[i + 1 - LOOK]) / LOOK
        smk = math.sqrt(max(sm2, 1e-10))
        mk12 = (P.Cm[i + 1] - P.Cm[i + 1 - LOOK]) / (smk * math.sqrt(252))
        f.append(np.full(A, _sc(mk12, 4.0)))
        disp = np.std(mv) if v.sum() > 1 else 0.0
        f.append(np.full(A, _sc(math.log(max(disp, 1e-4) / 0.2), 3.0)))
        F[q] = np.stack(f, axis=-1)
        V[q] = v
    F[~V] = 0.0
    return F, V


def rule_weights(F, V, frac=1 / 3):
    """Top third by raw 12-1 momentum (feature 6), equal weight."""
    W = np.zeros(V.shape)
    for q in range(len(V)):
        idx = np.flatnonzero(V[q])
        if len(idx) == 0:
            continue
        k = max(1, int(round(len(idx) * frac)))
        m = F[q, idx, 6]
        top = idx[np.argsort(-m, kind="stable")[:k]]
        W[q, top] = 1.0 / k
    return W


def labels(P: Prep, dec_rows, last_row):
    """Holding-period gross growth per industry for decision rows whose period ends <= last_row."""
    rows, G = [], []
    for k in range(len(dec_rows) - 1):
        t, t2 = dec_rows[k], dec_rows[k + 1]
        a, b = t + 1 + EXEC_LAG, t2 + EXEC_LAG
        if b > last_row:
            break
        rows.append(t)
        G.append(np.exp(P.C[b + 1] - P.C[a]))
    return np.array(rows, dtype=np.int64), np.array(G)


# ------------------------------------------------------------------------------ models
class Block(nn.Module):
    def __init__(self, d, heads, ff, drop):
        super().__init__()
        self.h = heads
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.qkv, self.proj = nn.Linear(d, 3 * d), nn.Linear(d, d)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.GELU(), nn.Linear(ff, d))
        self.drop = nn.Dropout(drop)

    def forward(self, x, mask):             # mask (B, N) True = valid
        B, N, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).view(B, N, 3, self.h, d // self.h).permute(2, 0, 3, 1, 4)
        s = q @ k.transpose(-1, -2) / math.sqrt(d // self.h)
        s = s.masked_fill(~mask[:, None, None, :], -1e9)
        a = (torch.softmax(s, dim=-1) @ v).transpose(1, 2).reshape(B, N, d)
        x = x + self.drop(self.proj(a))
        return x + self.drop(self.ff(self.ln2(x)))


class SetRanker(nn.Module):
    """Set-attention over industries; no identity embeddings; linear skip + attention path."""

    def __init__(self, nf=N_FEAT, d=32, heads=4, ff=64, layers=2, drop=0.1):
        super().__init__()
        self.emb = nn.Linear(nf, d)
        self.blocks = nn.ModuleList([Block(d, heads, ff, drop) for _ in range(layers)])
        self.ln = nn.LayerNorm(d)
        self.head = nn.Linear(d, 1)
        self.skip = nn.Linear(nf, 1, bias=False)
        for p in (self.head.weight, self.head.bias, self.skip.weight):
            nn.init.zeros_(p)

    def forward(self, F, mask):
        x = self.emb(F)
        for b in self.blocks:
            x = b(x, mask)
        return self.head(self.ln(x)).squeeze(-1) + self.skip(F).squeeze(-1)


class LinearRanker(nn.Module):
    def __init__(self, nf=N_FEAT):
        super().__init__()
        self.lin = nn.Linear(nf, 1, bias=False)
        nn.init.zeros_(self.lin.weight)

    def forward(self, F, mask):
        return self.lin(F).squeeze(-1)


def masked_softmax(s, mask):
    return torch.softmax(s.masked_fill(~mask, -1e9), dim=-1) * mask


def _growth_terms(W, G):
    """Per-month log growth net of costs (vs drifted previous weights)."""
    g = (W * G).sum(-1)
    drift = W[:-1] * G[:-1] / g[:-1, None]
    to = torch.cat([W[:1].abs().sum(-1), (W[1:] - drift).abs().sum(-1)])
    return torch.log(g) + torch.log(1 - COST * to)


def train_member(kind, F, V, G, train_m, val_m, seed, steps=400, lr=2e-3, wd=0.1,
                 eval_every=5, patience=12):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = SetRanker() if kind == "tf" else LinearRanker()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    Ft, Vt, Gt = (torch.tensor(F, dtype=torch.float32), torch.tensor(V),
                  torch.tensor(G, dtype=torch.float32))
    tm, vm = torch.tensor(train_m), torch.tensor(val_m)
    best, best_state, bad = -1e9, copy.deepcopy(model.state_dict()), 0
    for step in range(steps):
        model.train()
        W = masked_softmax(model(Ft, Vt), Vt)
        loss = -_growth_terms(W, Gt)[tm].mean()
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if (step + 1) % eval_every == 0:
            model.eval()
            with torch.no_grad():
                W = masked_softmax(model(Ft, Vt), Vt)
                sc = _growth_terms(W, Gt)[vm].mean().item()
            if sc > best + 1e-6:
                best, best_state, bad = sc, copy.deepcopy(model.state_dict()), 0
            else:
                bad += 1
                if bad >= patience:
                    break
    model.load_state_dict(best_state)
    model.eval()
    return model.double()


def fit_ensemble(kind, F, V, G, seed0, K=4, purge=1):
    m = len(G)
    edges = np.linspace(0, m, K + 1).astype(int)
    members = []
    for k in range(K):
        val = np.zeros(m, dtype=bool)
        val[edges[k]:edges[k + 1]] = True
        tr = np.ones(m, dtype=bool)
        tr[max(0, edges[k] - purge):min(m, edges[k + 1] + purge)] = False
        members.append(train_member(kind, F, V, G, tr, val, seed=seed0 * 10 + k))
    return members


def ensemble_weights(members, F, V):
    """Mean member weights, float64, per-date independent (batch invariant)."""
    with torch.no_grad():
        Ft, Vt = torch.tensor(F, dtype=torch.float64), torch.tensor(V)
        W = sum(masked_softmax(mm(Ft, Vt), Vt) for mm in members) / len(members)
    return W.numpy()


def topk_weights(S, V, frac=1 / 3):
    W = np.zeros(V.shape)
    for q in range(len(V)):
        idx = np.flatnonzero(V[q])
        if len(idx) == 0:
            continue
        k = max(1, int(round(len(idx) * frac)))
        top = idx[np.argsort(-S[q, idx], kind="stable")[:k]]
        W[q, top] = 1.0 / k
    return W
