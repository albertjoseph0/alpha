"""Core of the token-GPT strategy: tokenizer, tiny causal transformer, trainer, decoder.

"The market as a language" (Wolfram, what_is_chatgpt_doing_wolfram.txt pp. 10-16, 56-71):
  * a word = the excess log return of one asset over H trading days, measured in units of
    the volatility known before the word started (vol-normalised), then discretised into
    K equal-frequency bins -> a vocabulary of K tokens;
  * a sentence = the last L non-overlapping words of one asset, aligned so that the last
    word ends on the decision day (every day gives a differently-phased tokenisation of
    the same history: free data augmentation, Wolfram p. 48-49);
  * a second channel carries the market's word at the same position (cross-asset context);
  * token + channel + position embeddings are added (p. 64-65), passed through causal
    attention blocks (p. 65-69), and the last position is decoded by a softmax over the
    vocabulary (p. 69-70);
  * the "next token" is the next *tradable* word: the H-day return from t+2 to t+H+1,
    which matches the harness execution lag and keeps the day-t+1 stale-price
    autocorrelation out of the target (REVIEW.md s.5).

Everything here is deterministic given a seed. Inference runs in float64 so that the
output does not depend on the batch size (causality audit).
"""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(1)

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
VOL_HALFLIFE = 30      # days, EWMA half-life of the normalising volatility
VOL_WINDOW = 250       # days, the EWMA kernel is truncated here (batch invariance)
VOL_FLOOR = 1e-4       # daily vol floor (log units)


def _vol_kernel() -> np.ndarray:
    lam = 0.5 ** (1.0 / VOL_HALFLIFE)
    w = lam ** np.arange(VOL_WINDOW, dtype=np.float64)
    return w / w.sum()


_KERNEL = _vol_kernel()


def ewma_vol(x: np.ndarray) -> np.ndarray:
    """Trailing daily vol with a fixed-length kernel: row t depends only on rows t-W+1..t.

    x: (T, A) daily excess log returns. Returns (T, A); NaN for the first W-1 rows.
    """
    T, A = x.shape
    out = np.full((T, A), np.nan)
    if T < VOL_WINDOW:
        return out
    sq = x * x
    # correlate(sq, kernel) with kernel[0] on the most recent day
    k = _KERNEL[::-1]  # oldest-first weights
    win = np.lib.stride_tricks.sliding_window_view(sq, VOL_WINDOW, axis=0)  # (T-W+1, A, W)
    out[VOL_WINDOW - 1:] = np.sqrt(np.einsum("taw,w->ta", win, k))
    return np.maximum(out, VOL_FLOOR)


def hday_sum(x: np.ndarray, h: int) -> np.ndarray:
    """Row s = sum of rows s-h+1..s (NaN for s<h-1), computed per row (batch invariant)."""
    T, A = x.shape
    out = np.full((T, A), np.nan)
    if T >= h:
        win = np.lib.stride_tricks.sliding_window_view(x, h, axis=0)  # (T-h+1, A, h)
        out[h - 1:] = win.sum(axis=2)
    return out


def make_z(x: np.ndarray, h: int):
    """Vol-normalised H-day words.

    z_in[s]  = sum(x[s-h+1..s]) / (vol[s-h] * sqrt(h))       (input word ending at s)
    z_out[s] = sum(x[s+2..s+h+1]) / (vol[s] * sqrt(h))       (next tradable word after s)
    vol[s]   = trailing daily vol at s.
    """
    T, A = x.shape
    vol = ewma_vol(x)
    s = hday_sum(x, h)
    z_in = np.full((T, A), np.nan)
    z_in[h:] = s[h:] / (vol[:-h] * math.sqrt(h))
    z_out = np.full((T, A), np.nan)
    if T > h + 1:
        z_out[:T - h - 1] = s[h + 1:] / (vol[:T - h - 1] * math.sqrt(h))
    return z_in, z_out, vol


def tokenize(z: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Bin index 0..K-1; NaN -> -1."""
    tok = np.searchsorted(edges, z, side="right").astype(np.int64)
    tok[~np.isfinite(z)] = -1
    return tok


# ---------------------------------------------------------------------------
# Model: a tiny GPT
# ---------------------------------------------------------------------------
class Block(nn.Module):
    def __init__(self, d: int, n_head: int, d_ff: int, dropout: float):
        super().__init__()
        self.n_head = n_head
        self.ln1 = nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d)
        self.proj = nn.Linear(d, d)
        self.ln2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Linear(d, d_ff), nn.GELU(), nn.Linear(d_ff, d))
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        B, L, d = x.shape
        hd = d // self.n_head
        q, k, v = self.qkv(self.ln1(x)).split(d, dim=2)
        q = q.view(B, L, self.n_head, hd).transpose(1, 2)
        k = k.view(B, L, self.n_head, hd).transpose(1, 2)
        v = v.view(B, L, self.n_head, hd).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(hd)
        att = att.masked_fill(mask, float("-inf"))
        att = self.drop(torch.softmax(att, dim=-1))
        y = (att @ v).transpose(1, 2).reshape(B, L, d)
        x = x + self.drop(self.proj(y))
        x = x + self.drop(self.ff(self.ln2(x)))
        return x


class TinyGPT(nn.Module):
    def __init__(self, K: int, L: int, n_ch: int = 2, d: int = 32, n_layer: int = 2,
                 n_head: int = 2, d_ff: int = 64, dropout: float = 0.1):
        super().__init__()
        self.K, self.L, self.n_ch = K, L, n_ch
        self.tok = nn.ModuleList([nn.Embedding(K, d) for _ in range(n_ch)])
        self.pos = nn.Embedding(L, d)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList([Block(d, n_head, d_ff, dropout) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d)
        self.head = nn.Linear(d, K)
        self.register_buffer("mask", torch.triu(torch.ones(L, L, dtype=torch.bool), diagonal=1),
                             persistent=False)
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, std=0.02)
            nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, L, n_ch) int64 -> logits (B, L, K)."""
        B, L, _ = x.shape
        h = self.pos.weight[:L].unsqueeze(0)
        for c in range(self.n_ch):
            h = h + self.tok[c](x[:, :, c])
        h = self.drop(h)
        mask = self.mask[:L, :L]
        for blk in self.blocks:
            h = blk(h, mask)
        return self.head(self.ln_f(h))


# ---------------------------------------------------------------------------
# Corpus: token arrays for all assets
# ---------------------------------------------------------------------------
class Corpus:
    """Token arrays over the full available history.

    tok_in  (T, A): input words (own channel)
    tok_mkt (T,)  : market input word (second channel)
    tok_out (T, A): next tradable word (training target; -1 where unknown)
    """

    def __init__(self, x: np.ndarray, mkt_col: int, h: int, edges: np.ndarray):
        z_in, z_out, vol = make_z(x, h)
        self.z_in, self.z_out, self.vol = z_in, z_out, vol
        self.tok_in = tokenize(z_in, edges)
        self.tok_out = tokenize(z_out, edges)
        self.tok_mkt = self.tok_in[:, mkt_col]
        self.h = h

    def windows(self, a: np.ndarray, t: np.ndarray, L: int):
        """Contexts for (asset a_i, end day t_i): positions t - (L-1-k)h, k=0..L-1."""
        offs = self.h * np.arange(L - 1, -1, -1)
        idx = t[:, None] - offs[None, :]
        xin = np.stack([self.tok_in[idx, a[:, None]], self.tok_mkt[idx]], axis=-1)
        y = self.tok_out[idx, a[:, None]]
        return xin, y


def valid_ends(c: Corpus, L: int, a: int, t_max: int) -> np.ndarray:
    """End days t <= t_max whose whole context has valid input tokens and targets."""
    first = np.argmax((c.tok_in[:, a] >= 0) & (c.tok_mkt >= 0))
    t0 = first + c.h * (L - 1)
    t1 = t_max
    if t1 < t0:
        return np.empty(0, dtype=np.int64)
    return np.arange(t0, t1 + 1)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(model: TinyGPT, c: Corpus, assets: list[int], t_max: int, steps: int, seed: int,
          batch: int = 64, lr: float = 1e-3, wd: float = 0.1, log_every: int = 0,
          val: tuple | None = None) -> list:
    """Next-token training on random (asset, end-day) windows ending <= t_max.

    Every position of every window is a training target (GPT-style teacher forcing).
    Targets at position s use returns up to s+h+1 <= t_max + h + 1 ... so the caller must
    pass t_max = last_day - h - 1 to keep all targets inside the fit data.
    """
    L = model.L
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    pools = [(a, valid_ends(c, L, a, t_max)) for a in assets]
    pools = [(a, e) for a, e in pools if len(e)]
    sizes = np.array([len(e) for _, e in pools], dtype=float)
    probs = sizes / sizes.sum()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd, betas=(0.9, 0.95))
    model.train()
    hist = []
    for step in range(steps):
        which = rng.choice(len(pools), size=batch, p=probs)
        a = np.array([pools[i][0] for i in which])
        t = np.array([pools[i][1][rng.integers(len(pools[i][1]))] for i in which])
        xin, y = c.windows(a, t, L)
        xb = torch.from_numpy(xin)
        yb = torch.from_numpy(y)
        logits = model(xb)
        loss = F.cross_entropy(logits.reshape(-1, model.K), yb.reshape(-1), ignore_index=-1)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if log_every and (step + 1) % log_every == 0:
            rec = {"step": step + 1, "train": float(loss.detach())}
            if val is not None:
                rec["val"] = evaluate(model, c, *val)
                model.train()
            hist.append(rec)
    model.eval()
    return hist


@torch.no_grad()
def evaluate(model: TinyGPT, c: Corpus, assets: list[int], t_lo: int, t_hi: int,
             last_only: bool = True) -> float:
    """Mean CE of the last-position prediction for end days in [t_lo, t_hi] (every h-th day)."""
    model.eval()
    L = model.L
    losses = []
    for a in assets:
        e = valid_ends(c, L, a, t_hi)
        e = e[e >= t_lo][:: c.h]
        if not len(e):
            continue
        xin, y = c.windows(np.full(len(e), a), e, L)
        logits = model(torch.from_numpy(xin))
        if last_only:
            lg, yy = logits[:, -1], torch.from_numpy(y[:, -1])
        else:
            lg, yy = logits.reshape(-1, model.K), torch.from_numpy(y.reshape(-1))
        losses.append(F.cross_entropy(lg, yy, ignore_index=-1, reduction="none"))
    return float(torch.cat(losses).mean())


@torch.no_grad()
def predict_probs(models: list[TinyGPT], xin: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Ensemble-average softmax of the last position, in float64 (batch invariant)."""
    xb = torch.from_numpy(xin)
    out = None
    for m in models:
        logits = m(xb)[:, -1, :] / temperature
        p = torch.softmax(logits, dim=-1).numpy()
        out = p if out is None else out + p
    return out / len(models)
