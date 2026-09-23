"""Causal multifractal estimators on a single return series.

Every function takes a 1-D float64 array of daily log returns `r` (oldest first)
and returns an array of the same length whose entry t depends only on r[:t+1]
(trailing windows built from cumulative sums over the prefix, so the value at t
is bit-identical whatever data follows t). Entries without enough history are NaN.

References (research/extracted/):
  dynamics_of_financial_markets.txt  p.6  zeta_q = q(1/2+lambda^2) - lambda^2 q^2/2, lambda^2 ~ 0.03
                                      p.8  Var[ln sigma_tau] = -lambda^2 ln tau + V0 (cascade)
                                      p.9-11 MRW: Cov(omega_i, omega_j) = lambda^2 ln(T/|i-j|)
                                      p.12 mug shots: long-horizon vol drives short-horizon vol
  misbehavior_of_markets_mandelbrot.txt p.245 (book p.217) f(alpha) spectrum, multifractal time
                                      p.320-321 box-counting dimension
"""
from __future__ import annotations

import numpy as np

_EPS_ABS = 1e-4  # floor for |r| before taking logs (1bp); daily index returns are rarely below it


def _csum(x: np.ndarray) -> np.ndarray:
    """Cumulative sum with a leading zero: S[k] = sum(x[:k])."""
    out = np.empty(len(x) + 1)
    out[0] = 0.0
    np.cumsum(x, out=out[1:])
    return out


def _roll_sum(x: np.ndarray, w: int) -> np.ndarray:
    """sum(x[t-w+1 : t+1]) at each t (NaN for t < w-1)."""
    s = _csum(x)
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = s[w:] - s[:-w]
    return out


def ewm_var(r: np.ndarray, halflife: float) -> np.ndarray:
    """Causal EWMA of r^2 (recursive, so prefix-invariant)."""
    a = 1.0 - 0.5 ** (1.0 / halflife)
    out = np.empty(len(r))
    v = np.nan
    for i, x in enumerate(r):
        x2 = x * x
        v = x2 if not np.isfinite(v) else (1 - a) * v + a * x2
        out[i] = v
    return out


def rolling_vol(r: np.ndarray, w: int) -> np.ndarray:
    """Root mean square of r over the trailing w days."""
    return np.sqrt(_roll_sum(r * r, w) / w)


def lambda2_logcov(r: np.ndarray, window: int = 1008,
                   lags=(1, 2, 3, 5, 8, 13, 21, 34, 55, 89)) -> np.ndarray:
    """Intermittency coefficient from the MRW log-volatility covariance.

    omega_t = ln|r_t|. In the MRW, Cov(omega_t, omega_{t+l}) = lambda^2 ln(T/l) for
    l >= 1 (the i.i.d. ln|eps| noise only affects lag 0), so lambda^2 = -slope of
    the lagged covariance against ln(l). Estimated in a trailing window.
    """
    om = np.log(np.abs(r) + _EPS_ABS)
    n = len(om)
    lags = np.asarray(lags, dtype=int)
    covs = np.full((len(lags), n), np.nan)
    for j, l in enumerate(lags):
        m = window - l
        prod = np.zeros(n)
        prod[l:] = om[l:] * om[:-l]
        sxy = _roll_sum(prod, m)                         # sum over i in (t-m, t] of om_i om_{i-l}
        sx = _roll_sum(om, m)                            # om_i, i in (t-m, t]
        sy = np.full(n, np.nan)
        sy[l:] = _roll_sum(om, m)[:-l]                   # om_{i-l}
        c = sxy / m - (sx / m) * (sy / m)
        c[: window - 1] = np.nan
        covs[j] = c
    x = np.log(lags.astype(float))
    xc = x - x.mean()
    slope = (xc[:, None] * covs).sum(0) / (xc ** 2).sum()
    return -slope


def zeta_curvature(r: np.ndarray, window: int = 1008, scales=(1, 2, 4, 8, 16, 32),
                   qs=(1.0, 2.0, 3.0, 4.0)):
    """Structure-function scaling exponents in a trailing window.

    M_q(tau) = mean |R_tau|^q with R_tau the (overlapping) tau-day return, demeaned
    by the window's drift. zeta_q = slope of ln M_q vs ln tau. The parabola
    zeta_q = c1 q - c2 q^2/2 is fitted by least squares and c2 is the
    curvature-based lambda^2 (Borland et al. p.6). Returns (lambda2, h) where
    h = zeta_2/2 (the Hurst-like exponent of the second moment).
    """
    n = len(r)
    cr = _csum(r)
    scales = np.asarray(scales, dtype=int)
    qs = np.asarray(qs, dtype=float)
    lnM = np.full((len(qs), len(scales), n), np.nan)
    mu = _roll_sum(r, window) / window                   # drift per day in the window
    for k, tau in enumerate(scales):
        R = np.full(n, np.nan)
        R[tau - 1:] = cr[tau:] - cr[:-tau]
        # Demean each increment with the trailing-window drift at its own end date
        # (causal; E|R - tau*mu|^q is not separable in the evaluation date's drift).
        Rd = R - tau * np.nan_to_num(mu)
        for iq, q in enumerate(qs):
            a = np.abs(Rd) ** q
            a[np.isnan(a)] = 0.0
            m = window - tau + 1
            s = _roll_sum(a, m) / m
            s[: window - 1 + 0] = np.nan
            lnM[iq, k] = np.log(s)
    x = np.log(scales.astype(float))
    xc = x - x.mean()
    zeta = (xc[None, :, None] * lnM).sum(1) / (xc ** 2).sum()   # (nq, n)
    # least squares fit zeta_q = c1 q - c2 q^2 / 2
    A = np.stack([qs, -0.5 * qs ** 2], axis=1)                  # (nq, 2)
    P = np.linalg.pinv(A)                                       # (2, nq)
    c = P @ zeta                                                # (2, n)
    lam2 = c[1]
    h = zeta[list(qs).index(2.0)] / 2.0 if 2.0 in list(qs) else np.full(n, np.nan)
    return lam2, h


def holder_local(r: np.ndarray, scales=(2, 4, 8, 16, 32, 64, 128)) -> np.ndarray:
    """Local Hoelder exponent of the activity measure mu(t, s) = sum_{last s days} |r|.

    mu(t, s) ~ s^alpha(t): alpha = 1 for homogeneous activity, alpha < 1 when the
    most recent days carry a burst of activity (a singularity of the multifractal
    trading-time measure), alpha > 1 when the recent past is unusually calm.
    """
    a = np.abs(r)
    scales = np.asarray(scales, dtype=int)
    lnmu = np.stack([np.log(_roll_sum(a, s)) for s in scales])
    x = np.log(scales.astype(float))
    xc = x - x.mean()
    return (xc[:, None] * lnmu).sum(0) / (xc ** 2).sum()


def logvol_scale_slope(r: np.ndarray, window: int = 1008, scales=(5, 10, 21, 42, 63)) -> np.ndarray:
    """Cascade estimate of lambda^2 from Var[ln sigma_tau] = -lambda^2 ln tau + V0 (p.8).

    sigma_tau is the realized vol over non-overlapping blocks of tau days ending at
    t, t-tau, ... inside the trailing window. The chi-square sampling noise of a
    tau-day realized variance adds ~1/(2 tau) to Var[ln sigma]; it is subtracted.
    """
    n = len(r)
    r2 = r * r
    out = np.full(n, np.nan)
    scales = np.asarray(scales, dtype=int)
    rs = [_roll_sum(r2, int(s)) for s in scales]
    x = np.log(scales.astype(float))
    xc = x - x.mean()
    for t in range(window - 1, n):
        v = np.empty(len(scales))
        for k, s in enumerate(scales):
            idx = np.arange(t, t - window + s - 1, -s)
            lv = 0.5 * np.log(rs[k][idx] / s)
            v[k] = lv.var() - 1.0 / (2.0 * s)
        out[t] = -(xc * v).sum() / (xc ** 2).sum()
    return out


def fractal_dimension(logp: np.ndarray, n: int = 63) -> np.ndarray:
    """Box-counting style dimension of the price path over 2n days (FRAMA form).

    N1, N2 = range of each half / n, N3 = range over 2n / 2n,
    D = (ln(N1 + N2) - ln N3) / ln 2 : 1 = smooth trend, 1.5 = random walk, 2 = space filling.
    """
    L = len(logp)
    out = np.full(L, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view as swv
    if L < 2 * n:
        return out
    win = swv(logp, 2 * n)                                     # win[k] covers k .. k+2n-1
    h1, h2 = win[:, :n], win[:, n:]
    N1 = (h1.max(1) - h1.min(1)) / n
    N2 = (h2.max(1) - h2.min(1)) / n
    N3 = (win.max(1) - win.min(1)) / (2 * n)
    with np.errstate(divide="ignore", invalid="ignore"):
        D = (np.log(N1 + N2) - np.log(N3)) / np.log(2.0)
    out[2 * n - 1:] = D
    return out
