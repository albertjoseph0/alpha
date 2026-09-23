"""Synthetic multifractal markets for pretraining (the "simulated data" of Wolfram pp. 48-49).

Three generators from the source documents, each with parameters drawn from broad priors
centred on *generic literature values* (no estimation from real data happens here):

1. MRW + leverage  -- Bacry-Muzy-Delour multifractal random walk, Borland et al. (2005)
   eqs. 10-12 (pp. 8-10), in its causal form: log-vol is a sum of past Gaussian shocks with
   a kernel ~ 1/sqrt(lag) cut at the integral time T (p. 10), intermittency lambda^2 ~ 0.03
   (p. 5).  MRW alone is time-reversal symmetric (sec. 5.4, p. 12), so log-vol is also
   driven by *past* standardized returns with a negative, decaying kernel (the leverage
   correlation of ref [34], p. 12).  Residuals are Student-t (tail exponent mu ~ 3-5, p. 4).
2. Multi-timescale ARCH / statistical feedback -- Borland et al. eqs. 14-15 (pp. 13-14):
   sigma_i^2 = s0^2 + sum_k K(k) G(r~_{i,k}),  G(r) = g1 r + g2 r^2,  g1 < 0 (leverage),
   K(k) a power law over horizons k = 1..512 days.  Time-asymmetric by construction.
3. MMAR -- Mandelbrot's Brownian motion in multifractal trading time (book ch. XI,
   pp. 240-245): a randomized multiplicative cascade (the 60/40 "binomial bending of time",
   p. 243) deforms clock time; price is a Brownian motion of trading time.

Every path optionally receives stale-price smoothing (observed AR(1) of +0 to +0.3, as in
the real dev-period index data, REVIEW.md sec. 5) and a random drift.  Output: daily log
returns, one row per path.
"""
from __future__ import annotations

import numpy as np

DAY_VOL = 0.01  # arbitrary; all model inputs/targets are scale-free


def _fft_causal_conv(x: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """y[:, i] = sum_{k>=0} kernel[k] * x[:, i-k]  (rows are independent paths)."""
    n = x.shape[1]
    m = 1 << int(np.ceil(np.log2(n + len(kernel))))
    y = np.fft.irfft(np.fft.rfft(x, m, axis=1) * np.fft.rfft(kernel, m)[None, :], m, axis=1)
    return y[:, :n]


def _student_t(rng, shape, nu):
    """Unit-variance Student-t draws; nu is broadcast along axis 0."""
    nu = np.asarray(nu, dtype=float).reshape(-1, *([1] * (len(shape) - 1)))
    z = rng.standard_normal(shape)
    chi = rng.chisquare(np.broadcast_to(nu, shape))
    return z / np.sqrt(chi / nu) * np.sqrt((nu - 2.0) / nu)


def mrw_leverage(rng, n_paths: int, n: int) -> np.ndarray:
    lam2 = rng.uniform(0.015, 0.06, n_paths)            # intermittency, lit. ~0.03
    T = np.exp(rng.uniform(np.log(250), np.log(2500), n_paths)).astype(int)  # a few years
    nu = rng.uniform(3.5, 10.0, n_paths)                # residual tails
    gam = rng.uniform(0.05, 0.40, n_paths)              # leverage strength
    tau_l = np.exp(rng.uniform(np.log(5), np.log(60), n_paths))  # leverage memory (days)
    burn = 2600
    N = n + burn
    eps = _student_t(rng, (n_paths, N), nu)
    eta = rng.standard_normal((n_paths, N))
    omega = np.empty((n_paths, N))
    lev = np.empty((n_paths, N))
    k = np.arange(N, dtype=float)
    for p in range(n_paths):
        ker = np.where(k < T[p], 1.0 / np.sqrt(k + 1.0), 0.0) * np.sqrt(lam2[p])
        omega[p] = _fft_causal_conv(eta[p:p + 1], ker)[0]
        kl = np.exp(-k / tau_l[p]); kl[0] = 0.0          # strictly past returns
        kl /= np.sqrt((kl ** 2).sum())
        lev[p] = _fft_causal_conv(eps[p:p + 1], kl)[0]
    omega = omega - gam[:, None] * lev
    omega -= omega[:, burn:].mean(axis=1, keepdims=True)
    r = DAY_VOL * np.exp(omega) * eps
    return r[:, burn:]


def zumbach_arch(rng, n_paths: int, n: int) -> np.ndarray:
    """Vectorised over paths, loop over time.  Horizons k = 2^j, j=0..9."""
    ks = 2 ** np.arange(10)
    alpha = rng.uniform(0.0, 0.35, n_paths)             # K(k) ~ k^-alpha on dyadic k (long memory)
    persist = rng.uniform(0.75, 0.93, n_paths)          # sum_k K(k) g2  (< 1 : stationary)
    g1 = -rng.uniform(0.0, 1.0, n_paths)                # leverage (g1 < 0)
    nu = rng.uniform(6.0, 20.0, n_paths)
    K = ks[None, :] ** (-alpha[:, None])
    K = K / K.sum(axis=1, keepdims=True) * persist[:, None]      # includes g2 = 1
    s0sq = DAY_VOL ** 2 * (1.0 - persist)
    burn = 3000
    N = n + burn
    eps = _student_t(rng, (n_paths, N), nu)
    maxk = ks[-1]
    x = np.zeros((n_paths, N + maxk + 1))               # log-price with zero pre-history
    r = np.empty((n_paths, N))
    kidx = maxk - ks                                    # offsets into the ring
    sq_ks = np.sqrt(ks)[None, :]
    for i in range(N):
        cur = x[:, i + maxk]
        past = x[:, i + kidx]                           # x_{i-k}
        rt = (cur[:, None] - past) / sq_ks              # r~_{i,k}
        var = s0sq + (K * (rt ** 2)).sum(1) + DAY_VOL * g1 * (K * rt).sum(1)
        var = np.maximum(var, 0.04 * s0sq + 1e-10)
        ri = np.sqrt(var) * eps[:, i]
        r[:, i] = ri
        x[:, i + maxk + 1] = cur + ri
    return r[:, burn:]


def mmar_cascade(rng, n_paths: int, n: int) -> np.ndarray:
    """Brownian motion in multifractal trading time; randomized binomial cascade."""
    levels = int(np.ceil(np.log2(n)))
    m0 = rng.uniform(0.55, 0.68, n_paths)                # Mandelbrot's 60/40 example
    nu = rng.uniform(5.0, 30.0, n_paths)
    out = np.empty((n_paths, n))
    for p in range(n_paths):
        mass = np.ones(1)
        for _ in range(levels):
            left = np.where(rng.random(mass.size) < 0.5, m0[p], 1.0 - m0[p])
            # log-normal jitter keeps the cascade from being too regular
            left = np.clip(left * np.exp(0.05 * rng.standard_normal(mass.size)), 0.05, 0.95)
            mass = np.stack([mass * left, mass * (1.0 - left)], axis=1).ravel()
        dtheta = mass[:n] / mass[:n].mean()
        eps = _student_t(rng, (1, n), np.array([nu[p]]))[0]
        out[p] = DAY_VOL * np.sqrt(dtheta) * eps
    return out


def _augment(rng, r: np.ndarray) -> np.ndarray:
    n_paths, n = r.shape
    # stale prices: observed return = geometric average of true returns (AC1 = rho)
    rho = np.where(rng.random(n_paths) < 0.6, rng.uniform(0.0, 0.3, n_paths), 0.0)
    out = np.empty_like(r)
    prev = np.zeros(n_paths)
    for i in range(n):
        prev = (1.0 - rho) * r[:, i] + rho * prev
        out[:, i] = prev
    # random volatility level and a drift with Sharpe in [-0.2, 0.8] (annual)
    lvl = np.exp(rng.uniform(np.log(0.5), np.log(2.0), n_paths))
    sd = out.std(axis=1, keepdims=True) + 1e-12
    sharpe = rng.uniform(-0.2, 0.8, n_paths)
    out = out / sd * DAY_VOL * lvl[:, None]
    out += (sharpe / np.sqrt(252.0) * DAY_VOL * lvl)[:, None]
    return out


def generate(seed: int, n_paths: int, n: int, mix=(0.45, 0.35, 0.20)) -> np.ndarray:
    """Synthetic daily log-returns, shape (n_paths, n).  Deterministic given seed."""
    rng = np.random.default_rng(seed)
    counts = np.floor(np.asarray(mix) * n_paths).astype(int)
    counts[0] += n_paths - counts.sum()
    parts = [mrw_leverage(rng, counts[0], n), zumbach_arch(rng, counts[1], n),
             mmar_cascade(rng, counts[2], n)]
    r = np.concatenate(parts, axis=0)
    r = _augment(rng, r)
    return r[rng.permutation(n_paths)]
