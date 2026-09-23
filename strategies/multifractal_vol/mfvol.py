"""Volatility forecasters for the multifractal_vol strategy.

All functions are causal: the value at index t uses returns r[0..t] only.
Forecast target: sum of squared daily log returns over days t+2 .. t+1+H
(the harness executes a decision made at close t at close t+1, so the first
return earned is t+2).

Models
------
ewma_var          RiskMetrics EWMA baseline (lambda = 0.94).
garch_fit/_fc     GARCH(1,1) / GJR-GARCH(1,1) Gaussian QMLE baseline.
mrw_*             Multifractal Random Walk (Bacry-Muzy-Delour, Borland et al.
                  eqs. 10-12): log-vol is Gaussian with covariance
                  lambda^2 ln(T/(tau+1)); the optimal linear predictor of future
                  log-vol from past log|r| is solved from that covariance
                  (Wiener-Kolmogorov / Toeplitz system).
mtarch_*          Multi-timescale ARCH with leverage (Borland et al. eq. 15):
                  sigma^2 = s0 + sum_k K(k) [g2 rt_k^2 + g1 rt_k], rt_k the
                  k-day return normalised by sqrt(k), power-law kernel K(k).
msm_*             Calvet-Fisher binomial Markov-Switching Multifractal,
                  fitted by maximum likelihood (batched grid + Nelder-Mead).
"""
from __future__ import annotations

import numpy as np
from scipy import linalg, optimize, signal

H_DEFAULT = 21
LAG = 1  # execution lag of the harness: first earned return is t + LAG + 1


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def fwd_rv(lr: np.ndarray, H: int = H_DEFAULT, lag: int = LAG) -> np.ndarray:
    """Target: sum_{j=lag+1}^{lag+H} lr[t+j]^2 (NaN where not observable)."""
    r2 = lr ** 2
    c = np.concatenate([[0.0], np.cumsum(r2)])
    n = len(lr)
    out = np.full(n, np.nan)
    t = np.arange(n)
    hi = t + lag + H
    ok = hi <= n - 1
    out[ok] = c[hi[ok] + 1] - c[t[ok] + lag + 1]
    return out


def past_rv(lr: np.ndarray, k: int) -> np.ndarray:
    """Mean squared return over the last k days ending at t (causal)."""
    r2 = lr ** 2
    c = np.concatenate([[0.0], np.cumsum(r2)])
    n = len(lr)
    out = np.full(n, np.nan)
    t = np.arange(k - 1, n)
    out[t] = (c[t + 1] - c[t + 1 - k]) / k
    return out


# ----------------------------------------------------------------------------
# EWMA baseline
# ----------------------------------------------------------------------------
def ewma_var(lr: np.ndarray, lam: float = 0.94, init: float | None = None) -> np.ndarray:
    """Daily variance estimate at t (uses r up to t)."""
    r2 = lr ** 2
    v0 = float(np.mean(r2[:250])) if init is None else init
    y, _ = signal.lfilter([1 - lam], [1, -lam], r2, zi=[lam * v0])
    return y


# ----------------------------------------------------------------------------
# GARCH(1,1) / GJR baseline
# ----------------------------------------------------------------------------
def _garch_filter(lr, omega, alpha, beta, gamma, v0):
    """sigma2[t] = conditional variance of r[t+1] given r[..t]."""
    r2 = lr ** 2
    u = alpha * r2 + gamma * r2 * (lr < 0)
    y, _ = signal.lfilter([1.0], [1, -beta], omega + u, zi=[beta * v0])
    return y


def garch_fit(lr: np.ndarray, gjr: bool = False) -> dict:
    v0 = float(np.var(lr))
    r2 = lr ** 2

    def nll(p):
        a, b = p[0], p[1]
        g = p[2] if gjr else 0.0
        pers = a + b + g / 2
        if a < 0 or b < 0 or (g < 0 and a + g < 0) or pers >= 0.9999:
            return 1e10
        om = v0 * (1 - pers)
        s = _garch_filter(lr, om, a, b, g, v0)
        s = np.concatenate([[v0], s[:-1]])  # variance for r[t] given r[..t-1]
        s = np.maximum(s, 1e-12)
        return 0.5 * np.sum(np.log(s) + r2 / s)

    x0 = [0.06, 0.92, 0.04] if gjr else [0.08, 0.9]
    res = optimize.minimize(nll, x0, method="Nelder-Mead",
                            options={"xatol": 1e-5, "fatol": 1e-3, "maxiter": 2000})
    a, b = res.x[0], res.x[1]
    g = res.x[2] if gjr else 0.0
    pers = a + b + g / 2
    return {"alpha": a, "beta": b, "gamma": g, "V": v0, "omega": v0 * (1 - pers), "pers": pers}


def garch_forecast(lr: np.ndarray, p: dict, H: int = H_DEFAULT, lag: int = LAG) -> np.ndarray:
    """Sum of expected variances over t+lag+1 .. t+lag+H."""
    s1 = _garch_filter(lr, p["omega"], p["alpha"], p["beta"], p["gamma"], p["V"])  # var of t+1
    V, ph = p["V"], p["pers"]
    hs = np.arange(lag + 1, lag + H + 1)  # steps ahead
    wsum = np.sum(ph ** (hs - 1))
    return H * V + wsum * (s1 - V)


# ----------------------------------------------------------------------------
# MRW optimal linear predictor of log-volatility
# ----------------------------------------------------------------------------
ETA_VAR = np.pi ** 2 / 8  # Var[log|eps|] for Gaussian eps
ETA_MEAN = -0.6351814     # E[log|eps|] for standard Gaussian eps


def logabs(lr: np.ndarray, floor: float = 1e-4) -> np.ndarray:
    return np.log(np.maximum(np.abs(lr), floor))


def mrw_logcov_fit(y: np.ndarray, taus=None) -> tuple[float, float]:
    """Fit Cov(y_t, y_{t+tau}) = lambda^2 ln(T/tau) for tau in `taus`.

    Returns (lambda2, T). y is log|r| (observation noise is white, so it does
    not affect covariances at tau >= 1).
    """
    if taus is None:
        taus = np.unique(np.round(np.logspace(0, np.log10(500), 25)).astype(int))
    yc = y - y.mean()
    n = len(yc)
    cov = np.array([np.dot(yc[:n - k], yc[k:]) / (n - k) for k in taus])
    A = np.vstack([np.ones_like(taus, dtype=float), -np.log(taus)]).T
    coef, *_ = np.linalg.lstsq(A, cov, rcond=None)
    c0, lam2 = coef
    lam2 = max(lam2, 1e-4)
    T = float(np.exp(c0 / lam2))
    return float(lam2), T


def mrw_weights(lam2: float, T: float, L: int, H: int = H_DEFAULT, lag: int = LAG,
                eta_var: float = ETA_VAR) -> np.ndarray:
    """Weights w (len L, w[0] = most recent) of the best linear predictor of
    mean_{h=lag+1..lag+H} xi_{t+h} from y_{t}, ..., y_{t-L+1}.

    Covariance of xi: C(tau) = lam2 * ln(T / (tau + 1)) for tau + 1 < T else 0
    (Borland et al. eq. 11). y = xi + eta with white eta.
    """
    def C(tau):
        tau = np.asarray(tau, dtype=float)
        return np.where(tau + 1 < T, lam2 * np.log(T / (tau + 1)), 0.0)

    col = C(np.arange(L))
    col = col.astype(float).copy()
    col[0] += eta_var
    j = np.arange(L)
    hs = np.arange(lag + 1, lag + H + 1)
    rhs = np.mean([C(h + j) for h in hs], axis=0)
    w = linalg.solve_toeplitz(col, rhs)
    return w


def mrw_signal(y: np.ndarray, w: np.ndarray, mu: float) -> np.ndarray:
    """Predicted mean log-vol deviation: sum_j w[j] (y[t-j] - mu). Causal."""
    L = len(w)
    x = y - mu
    s = signal.lfilter(w, [1.0], x)
    s[:L - 1] = np.nan
    return s


# ----------------------------------------------------------------------------
# Multi-timescale ARCH with leverage (Borland et al. eq. 15), direct form
# ----------------------------------------------------------------------------
MT_SCALES = np.array([1, 2, 4, 8, 16, 32, 64, 128, 256])


def mtarch_features(lx: np.ndarray, scales=MT_SCALES) -> tuple[np.ndarray, np.ndarray]:
    """rt[t, k] = (x_t - x_{t-k}) / sqrt(k) for each scale k (x = cum log price)."""
    n = len(lx)
    x = np.concatenate([[0.0], np.cumsum(lx)])  # x[t+1] = log price after day t
    R = np.full((n, len(scales)), np.nan)
    for j, k in enumerate(scales):
        t = np.arange(k - 1, n)
        R[t, j] = (x[t + 1] - x[t + 1 - k]) / np.sqrt(k)
    return R ** 2, R


def mtarch_design(R2, R, alpha):
    """Power-law kernel K(k) ~ k^-alpha over log-spaced scales (each scale k
    stands for ~k lags, hence the extra factor k)."""
    k = MT_SCALES.astype(float)
    K = k ** (1 - alpha)
    K = K / K.sum()
    return R2 @ K, R @ K


def mtarch_fit(lr: np.ndarray, target: np.ndarray, alphas=np.linspace(0.6, 1.6, 11),
               H: int = H_DEFAULT) -> dict:
    """Fit target/H = s0 + g2 * sum K r2 + g1 * sum K r  by least squares on
    log-residual-robust QLIKE-ish weights; alpha on a small grid."""
    R2, R = mtarch_features(lr)
    ok = np.isfinite(target) & np.all(np.isfinite(R2), axis=1)
    y = target[ok] / H
    best = None
    for a in alphas:
        q2, q1 = mtarch_design(R2[ok], R[ok], a)
        X = np.vstack([np.ones_like(q2), q2, q1]).T
        # weighted LS with weights 1/fit^2 (approx QLIKE / heteroskedastic), 3 passes
        wts = np.ones_like(y)
        for _ in range(3):
            Xw = X * wts[:, None]
            coef, *_ = np.linalg.lstsq(Xw, y * wts, rcond=None)
            f = np.maximum(X @ coef, 1e-8)
            wts = 1.0 / f
        f = np.maximum(X @ coef, 1e-8)
        ql = np.mean(y / f - np.log(y / f + 1e-300) - 1)
        if best is None or ql < best[0]:
            best = (ql, a, coef)
    _, a, coef = best
    return {"alpha": a, "s0": coef[0], "g2": coef[1], "g1": coef[2]}


def mtarch_forecast(lr: np.ndarray, p: dict, H: int = H_DEFAULT, floor_frac: float = 0.1) -> np.ndarray:
    R2, R = mtarch_features(lr)
    q2, q1 = mtarch_design(R2, R, p["alpha"])
    f = p["s0"] + p["g2"] * q2 + p["g1"] * q1
    base = p["s0"] + p["g2"] * np.nanmedian(q2)
    return H * np.maximum(f, floor_frac * base)


# ----------------------------------------------------------------------------
# Calvet-Fisher binomial Markov-Switching Multifractal
# ----------------------------------------------------------------------------
def _msm_states(kbar: int, m0: np.ndarray) -> np.ndarray:
    """Product of multipliers for each of 2^kbar states; m0 shape (P,)."""
    bits = ((np.arange(2 ** kbar)[:, None] >> np.arange(kbar)[None, :]) & 1).astype(float)
    # state value: prod_k (m0 if bit else 2 - m0)
    lm1 = np.log(m0)[:, None, None]
    lm2 = np.log(2 - m0)[:, None, None]
    logM = (bits[None] * lm1 + (1 - bits[None]) * lm2).sum(-1)  # (P, S)
    return np.exp(logM)


def _msm_gammas(kbar, b, g_kbar):
    k = np.arange(1, kbar + 1)[None, :]
    return 1 - (1 - g_kbar[:, None]) ** (b[:, None] ** (k - kbar))  # (P, kbar)


def msm_filter(lr: np.ndarray, params: np.ndarray, kbar: int, return_probs: bool = False):
    """Batched Hamilton filter. params (P, 4): m0, sigma(daily), b, gamma_kbar.

    Returns log-likelihood (P,), and optionally the predictive state
    probabilities for r[t+1] given r[..t] for the first parameter set.
    """
    P = params.shape[0]
    m0, sig, b, gk = params.T
    S = 2 ** kbar
    M = _msm_states(kbar, m0)                     # (P, S)
    var = (sig[:, None] ** 2) * M                 # (P, S)
    g = _msm_gammas(kbar, b, gk)                  # (P, kbar)
    inv2v = 0.5 / var
    lognorm = -0.5 * np.log(2 * np.pi * var)
    pi = np.full((P, S), 1.0 / S)
    shape = (P,) + (2,) * kbar
    ll = np.zeros(P)
    n = len(lr)
    keep = np.empty((n, S)) if return_probs else None
    r2 = lr ** 2
    for t in range(n):
        # predictive distribution for r[t] is pi (already propagated)
        if return_probs:
            keep[t] = pi[0]
        dens = np.exp(lognorm - r2[t] * inv2v)
        num = pi * dens
        tot = num.sum(1)
        tot = np.maximum(tot, 1e-300)
        ll += np.log(tot)
        pi = num / tot[:, None]
        # propagate: each component switches with prob g_k to a fresh draw
        x = pi.reshape(shape)
        for k in range(kbar):
            ax = kbar - k  # bit k is axis (kbar - k) in C-order reshape
            gk_ = g[:, k].reshape((P,) + (1,) * kbar)
            x = (1 - gk_) * x + gk_ * 0.5 * x.sum(axis=ax, keepdims=True)
        pi = x.reshape(P, S)
    if return_probs:
        return ll, keep
    return ll


def msm_fit(lr: np.ndarray, kbar: int = 6, seed: int = 0) -> np.ndarray:
    """Coarse batched grid search, then Nelder-Mead on the best point."""
    sd = float(np.std(lr))
    grid = []
    for m0 in [1.2, 1.35, 1.5, 1.65, 1.8]:
        for b in [2.0, 3.0, 5.0, 8.0]:
            for gk in [0.2, 0.5, 0.8]:
                grid.append([m0, sd, b, gk])
    grid = np.array(grid)
    ll = msm_filter(lr, grid, kbar)
    p0 = grid[np.argmax(ll)]

    def to_x(p):
        return np.array([np.log((p[0] - 1) / (2 - p[0])), np.log(p[1]), np.log(p[2] - 1),
                         np.log(p[3] / (1 - p[3]))])

    def to_p(x):
        return np.array([1 + 1 / (1 + np.exp(-x[0])), np.exp(x[1]), 1 + np.exp(x[2]),
                         1 / (1 + np.exp(-x[3]))])

    def nll(x):
        return -msm_filter(lr, to_p(x)[None], kbar)[0]

    res = optimize.minimize(nll, to_x(p0), method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 0.5, "maxiter": 150})
    return to_p(res.x)


def msm_forecast(lr: np.ndarray, p: np.ndarray, kbar: int, H: int = H_DEFAULT, lag: int = LAG) -> np.ndarray:
    """Expected sum of variances over t+lag+1..t+lag+H given r[..t].

    keep[t] is the predictive distribution for r[t] given r[..t-1]; the
    distribution for r[t+1] given r[..t] is the filtered distribution
    propagated once, i.e. keep[t+1]. We append one more propagation step.
    """
    _, keep = msm_filter(np.append(lr, 0.0), p[None], kbar, return_probs=True)
    # keep[t+1] = predictive for r[t+1] given r[..t]  (the appended 0 only affects keep[n+1], unused)
    pred = keep[1:len(lr) + 1]
    m0, sig, b, gk = p
    S = 2 ** kbar
    M = _msm_states(kbar, np.array([m0]))[0]
    var = sig ** 2 * M
    g = _msm_gammas(kbar, np.array([b]), np.array([gk]))[0]
    # expected variance h steps after the predictive step: componentwise decay
    # E[M_k(t+s)] relaxes to 1 at rate (1-g_k)^s; E[prod] is not factorised under
    # the posterior, so propagate the full vector v_s = A^s var.
    shape = (2,) * kbar
    v = var.copy()
    acc = np.zeros(S)
    for s in range(0, lag + H):
        if s >= lag:
            acc += v
        x = v.reshape(shape)
        for k in range(kbar):
            ax = kbar - 1 - k
            x = (1 - g[k]) * x + g[k] * 0.5 * x.sum(axis=ax, keepdims=True)
        v = x.reshape(S)
    return pred @ acc
