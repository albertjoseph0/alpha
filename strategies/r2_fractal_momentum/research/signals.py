"""Causal signal library for 49-industry fractal momentum research (12-1 window everywhere)."""
import numpy as np, pandas as pd

LOOK, SKIP = 252, 21


def tsum(x, w):
    """trailing sum over w rows ending at t (prefix sums; NaN before w-1)."""
    c = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    out = np.full(x.shape, np.nan)
    out[w - 1:] = c[w:] - c[:-w]
    return out


def lag(x, k):
    out = np.full(x.shape, np.nan)
    out[k:] = x[:-k]
    return out


def win(x, look=LOOK, skip=SKIP):
    """sum of x over (t-look, t-skip]."""
    return lag(tsum(x, look - skip), skip) if skip else tsum(x, look)


def trailing_sigma(r, w=LOOK):
    """std of daily log returns over the w days ending t-1 (strictly before t)."""
    s1, s2 = tsum(r, w), tsum(r * r, w)
    var = (s2 - s1 * s1 / w) / (w - 1)
    return lag(np.sqrt(np.maximum(var, 0)), 1)


def signal(kind, r, look=LOOK, skip=SKIP):
    """r: T x N daily log returns with NaN -> 0."""
    if kind == "mom":
        return win(r, look, skip)
    if kind.startswith("eff"):            # ruler efficiency: X / L_k over the same window
        k = int(kind[3:])
        Rk = np.abs(tsum(r, k)); Rk[np.isnan(Rk)] = 0
        L = win(Rk, look - k + 1, skip) / k
        return win(r, look, skip) / L
    if kind.startswith("tt"):             # trading-time z: X / sqrt(sum of k-day r^2 / k)
        k = int(kind[2:])
        Rk = tsum(r, k) ** 2; Rk[np.isnan(Rk)] = 0
        V = win(Rk, look - k + 1, skip) / k
        return win(r, look, skip) / np.sqrt(V)
    if kind.startswith(("jw", "jr", "noah")):   # Joseph without Noah: winsorise/remove |r| > c sigma
        c = float(kind.lstrip("jwrnoah"))
        sig = trailing_sigma(r)
        with np.errstate(invalid="ignore"):
            big = np.abs(r) > c * sig
        if kind.startswith("jw"):
            x = np.clip(r, -c * sig, c * sig)
        elif kind.startswith("jr"):
            x = np.where(big, 0.0, r)
        else:
            x = np.where(big, r - np.clip(r, -c * sig, c * sig), 0.0)
        x = np.where(np.isnan(sig), r, x)
        return win(x, look, skip)
    raise ValueError(kind)


def xs_rank(a):
    """cross-sectional percentile rank per row, NaN-aware."""
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy()
