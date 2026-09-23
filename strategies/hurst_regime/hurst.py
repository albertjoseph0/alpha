"""Hurst-exponent estimators (Joseph effect) used by the hurst_regime strategy.

All estimators take a 1-D float64 array of *increments* (returns) and return an
estimate of H for the integrated process:  H = 0.5 independent increments,
H > 0.5 persistent, H < 0.5 anti-persistent (Mandelbrot & Hudson 2004,
misbehavior_of_markets_mandelbrot.txt pp. 215-216, 229).

  * rs_hurst      classical rescaled-range (R/S) regression over block sizes
                  (Notes p. 326-327), with the Anis-Lloyd/Peters small-sample
                  expectation subtracted so that i.i.d. data give ~0.5.
  * lo_v          Lo's (1991) modified R/S statistic V_q (long-run variance in
                  the denominator), the "Lo critique" cited on p. 220.
  * dfa_hurst     detrended fluctuation analysis (order 1).
  * vt_hurst      variance-time / aggregated-variance scaling via overlapping
                  variance ratios  Var(sum of m) ~ m^{2H}.

Everything is deterministic float64 numpy; no state.
"""
from __future__ import annotations

import math

import numpy as np


# --------------------------------------------------------------------------- R/S
def _rs_at_scale(x: np.ndarray, n: int) -> float:
    k = len(x) // n
    if k < 1:
        return np.nan
    # use the most recent k*n points (window end is what matters for trading)
    blk = x[len(x) - k * n:].reshape(k, n)
    y = blk - blk.mean(axis=1, keepdims=True)
    z = np.cumsum(y, axis=1)
    r = np.maximum(z.max(axis=1), 0.0) - np.minimum(z.min(axis=1), 0.0)
    s = blk.std(axis=1)
    ok = s > 0
    if not ok.any():
        return np.nan
    return float(np.mean(r[ok] / s[ok]))


def expected_rs(n: int) -> float:
    """Anis-Lloyd (1976) expected R/S of n i.i.d. Gaussian draws (Peters 1994 corr.)."""
    i = np.arange(1, n, dtype=float)
    ssum = np.sum(np.sqrt((n - i) / i))
    if n <= 340:
        g = math.exp(math.lgamma((n - 1) / 2.0) - math.lgamma(n / 2.0)) / math.sqrt(math.pi)
    else:
        g = 1.0 / math.sqrt(n * math.pi / 2.0)
    return ((n - 0.5) / n) * g * ssum


_ERS_CACHE: dict[int, float] = {}


def _ers(n: int) -> float:
    v = _ERS_CACHE.get(n)
    if v is None:
        v = expected_rs(n)
        _ERS_CACHE[n] = v
    return v


def rs_hurst(x: np.ndarray, scales) -> float:
    """Anis-Lloyd-corrected R/S Hurst exponent: 0.5 + slope of log(RS/E[RS]) on log n."""
    x = np.asarray(x, dtype=float)
    ln, lr = [], []
    for n in scales:
        rs = _rs_at_scale(x, int(n))
        if np.isfinite(rs) and rs > 0:
            ln.append(math.log(n))
            lr.append(math.log(rs) - math.log(_ers(int(n))))
    if len(ln) < 2:
        return np.nan
    return 0.5 + float(np.polyfit(ln, lr, 1)[0])


def rs_hurst_raw(x: np.ndarray, scales) -> float:
    """Uncorrected classical R/S slope (biased upward in small samples)."""
    x = np.asarray(x, dtype=float)
    ln, lr = [], []
    for n in scales:
        rs = _rs_at_scale(x, int(n))
        if np.isfinite(rs) and rs > 0:
            ln.append(math.log(n))
            lr.append(math.log(rs))
    if len(ln) < 2:
        return np.nan
    return float(np.polyfit(ln, lr, 1)[0])


# ----------------------------------------------------------------- Lo modified R/S
def lo_v(x: np.ndarray, q: int) -> float:
    """Lo's modified rescaled range V_q = R / (sqrt(N) * S_q), Bartlett weights.

    Under short-memory H0, V has the Brownian-bridge-range law: mean sqrt(pi/2),
    95% acceptance region [0.809, 1.862].
    """
    x = np.asarray(x, dtype=float)
    N = len(x)
    y = x - x.mean()
    z = np.cumsum(y)
    r = max(z.max(), 0.0) - min(z.min(), 0.0)
    s2 = np.dot(y, y) / N
    for j in range(1, q + 1):
        g = np.dot(y[j:], y[:-j]) / N
        s2 += 2.0 * (1.0 - j / (q + 1.0)) * g
    if s2 <= 0:
        return np.nan
    return float(r / math.sqrt(N * s2))


def lo_hurst(x: np.ndarray, q: int) -> float:
    """Map Lo's V_q to an H-like number: 0.5 + log(V_q / E[V]) / log(N)."""
    v = lo_v(x, q)
    if not np.isfinite(v) or v <= 0:
        return np.nan
    return 0.5 + math.log(v / math.sqrt(math.pi / 2.0)) / math.log(len(x))


# -------------------------------------------------------------------------- DFA
def dfa_hurst(x: np.ndarray, scales) -> float:
    x = np.asarray(x, dtype=float)
    prof = np.cumsum(x - x.mean())
    ln, lf = [], []
    for n in scales:
        n = int(n)
        k = len(prof) // n
        if k < 2 or n < 4:
            continue
        blk = prof[len(prof) - k * n:].reshape(k, n)
        t = np.arange(n, dtype=float)
        t = t - t.mean()
        tt = np.dot(t, t)
        mu = blk.mean(axis=1, keepdims=True)
        b = (blk - mu) @ t / tt
        res = blk - mu - b[:, None] * t[None, :]
        f = math.sqrt(np.mean(res * res))
        if f > 0:
            ln.append(math.log(n))
            lf.append(math.log(f))
    if len(ln) < 2:
        return np.nan
    return float(np.polyfit(ln, lf, 1)[0])


# ------------------------------------------------------------------ variance-time
def vt_hurst(x: np.ndarray, scales) -> float:
    """H from overlapping variance ratios: log VR(m) = (2H-1) log m (through origin)."""
    x = np.asarray(x, dtype=float)
    N = len(x)
    y = x - x.mean()
    v1 = np.dot(y, y) / N
    if v1 <= 0:
        return np.nan
    c = np.concatenate([[0.0], np.cumsum(y)])
    lm, lv = [], []
    for m in scales:
        m = int(m)
        if m < 2 or m >= N // 2:
            continue
        s = c[m:] - c[:-m]
        # small-sample bias correction of the overlapping VR (Lo-MacKinlay)
        vm = np.dot(s, s) / ((N - m + 1) * (1.0 - m / N))
        lm.append(math.log(m))
        lv.append(math.log(vm / (m * v1)))
    if not lm:
        return np.nan
    lm = np.asarray(lm)
    lv = np.asarray(lv)
    return 0.5 + 0.5 * float(np.dot(lm, lv) / np.dot(lm, lm))


ESTIMATORS = {
    "rs": rs_hurst,
    "dfa": dfa_hurst,
    "vt": vt_hurst,
}
