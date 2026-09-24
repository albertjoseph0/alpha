"""Skewed-vol pricing of SPX puts from VIX/VIX3M/SKEW (no option chains needed).

Model (stated rule):
  * 30-day implied-vol slice = SSVI slice (Gatheral-Jacquier) in total variance
        w(k) = theta/2 * (1 + rho*psi*x + sqrt((psi*x + rho)^2 + 1 - rho^2)),  x = k/sqrt(theta),
    k = ln(K/F).  rho is fixed (wing-shape assumption, base -0.7); theta (ATM total variance) and
    psi (dimensionless skew/curvature) are solved EVERY DAY so that the model's own CBOE-style
    model-free 30-day variance equals VIX^2 and its CBOE-style risk-neutral skewness equals
    (100 - SKEW)/10.  Both integrals are truncated where the model OTM price < 0.05 index points,
    like CBOE's zero-bid truncation.
  * Other tenors: psi constant across tenors (SSVI with phi(theta) ~ theta^-1/2), ATM total
    variance scaled by the variance-swap term structure: VIX (30d), VIX3M (91d), VIX6M (182d),
    VIX1Y (365d), linear in total variance, flat rate below 30d.  Where VIX3M/6M/1Y are missing
    (before 2006-07 / 2008 / 2007) they are proxied by a log-log regression on VIX fitted on the
    DEV overlap 2006-07-17..2007-12-31 only (see calibrate_surface.py).
"""
import math
import numpy as np
from scipy.special import ndtr

KGRID = np.linspace(-3.0, 1.2, 1400)  # log-moneyness grid for integrals
DK = KGRID[1] - KGRID[0]


def ssvi_w(k, theta, psi, rho):
    x = k / math.sqrt(theta)
    return 0.5 * theta * (1 + rho * psi * x + np.sqrt((psi * x + rho) ** 2 + 1 - rho * rho))


def bs_otm_over_F(k, w):
    """OTM option price / F (undiscounted) for log-moneyness k and total variance w."""
    sw = np.sqrt(w)
    d1 = -k / sw + 0.5 * sw
    d2 = d1 - sw
    K = np.exp(k)
    put = K * ndtr(-d2) - ndtr(-d1)
    call = ndtr(d1) - K * ndtr(d2)
    return np.where(k < 0, put, call)


def model_moments(theta, psi, rho, pmin_over_F=0.0):
    """CBOE/BKM model-free VIX^2*T and skewness of ln(S_T/F) for one SSVI slice."""
    k = KGRID
    w = ssvi_w(k, theta, psi, rho)
    Q = bs_otm_over_F(k, w)
    if pmin_over_F > 0:
        # truncate outward from the money at the first strike whose price < pmin (CBOE zero-bid rule)
        lo = np.where((k < 0) & (Q < pmin_over_F))[0]
        hi = np.where((k > 0) & (Q < pmin_over_F))[0]
        mask = np.ones_like(k, bool)
        if len(lo):
            mask[: lo.max() + 1] = False
        if len(hi):
            mask[hi.min():] = False
        Q = np.where(mask, Q, 0.0)
    g = Q * np.exp(-k) * DK  # Q/K^2 dK with K=F e^k, in units of F
    V = np.sum(2 * (1 - k) * g)
    W = np.sum((6 * k - 3 * k * k) * g)
    X = np.sum((12 * k * k - 4 * k ** 3) * g)
    mu = -V / 2 - W / 6 - X / 24
    var = V - mu * mu
    skew = (W - 3 * mu * V + 2 * mu ** 3) / var ** 1.5
    vix2T = 2 * np.sum(g)  # 2*int Q/K^2 dK
    return vix2T, skew


def put_price(S, K, tau, r, q, theta_tau, psi, rho):
    """Model mid of a European put (index points)."""
    if tau <= 1e-6:
        return max(K - S, 0.0)
    F = S * math.exp((r - q) * tau)
    k = math.log(K / F)
    x = k / math.sqrt(theta_tau)
    w = 0.5 * theta_tau * (1 + rho * psi * x + math.sqrt((psi * x + rho) ** 2 + 1 - rho * rho))
    sw = math.sqrt(w)
    d1 = -k / sw + 0.5 * sw
    d2 = d1 - sw
    return math.exp(-r * tau) * (K * _N(-d2) - F * _N(-d1))


def put_iv(S, K, tau, r, q, theta_tau, psi, rho):
    F = S * math.exp((r - q) * tau)
    k = math.log(K / F)
    x = k / math.sqrt(theta_tau)
    w = 0.5 * theta_tau * (1 + rho * psi * x + math.sqrt((psi * x + rho) ** 2 + 1 - rho * rho))
    return math.sqrt(w / tau)


def _N(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def varswap_total_var(tau, v30, v91, v182, v365):
    """Linear interpolation of variance-swap total variance; vols in decimals, tau in years."""
    pts_t = [30 / 365, 91 / 365, 182 / 365, 1.0]
    pts_w = [v30 ** 2 * pts_t[0], v91 ** 2 * pts_t[1], v182 ** 2 * pts_t[2], v365 ** 2]
    # enforce non-decreasing total variance (calendar no-arb)
    for i in range(1, 4):
        pts_w[i] = max(pts_w[i], pts_w[i - 1])
    if tau <= pts_t[0]:
        return v30 ** 2 * tau
    for i in range(1, 4):
        if tau <= pts_t[i]:
            a = (tau - pts_t[i - 1]) / (pts_t[i] - pts_t[i - 1])
            return pts_w[i - 1] + a * (pts_w[i] - pts_w[i - 1])
    return pts_w[3] * tau  # beyond 1y (not used)


# ---------------------------------------------------------------------------------------------
# Merton jump-diffusion variant (base model after the 2026-09-22 chain check, see README):
#   log-return = diffusion(sigma) + Poisson(lambda) jumps ~ N(muJ, dJ^2).
#   Structural constants muJ, dJ fixed; sigma and lambda solved daily to VIX and SKEW (30d, with
#   CBOE-style truncation).  Other tenors: lambda kept, diffusion variance chosen so the model's
#   variance-swap total variance equals the interpolated VIX/VIX3M/VIX6M/VIX1Y curve.
# ---------------------------------------------------------------------------------------------
from scipy.stats import poisson as _poisson  # noqa: E402

NMAX = 40
_NS = np.arange(NMAX)


def merton_jump_varswap_rate(lam, muJ, dJ):
    m = math.exp(muJ + 0.5 * dJ * dJ) - 1
    return 2 * lam * (m - muJ)  # jump contribution to VIX^2 per unit time


def merton_otm_over_F(k, T, sig, lam, muJ, dJ):
    """OTM price/F (undiscounted) on a vector of log-moneyness k=ln(K/F)."""
    m = math.exp(muJ + 0.5 * dJ * dJ) - 1
    lt = lam * T
    n_eff = int(min(NMAX, max(10, lt + 8 * math.sqrt(lt + 1) + 5)))
    ns = _NS[:n_eff]
    wts = _poisson.pmf(ns, lt)
    K = np.exp(k)[:, None]
    lnFn = (-lam * m * T + ns * (muJ + 0.5 * dJ * dJ))[None, :]
    v = np.sqrt(sig * sig * T + ns * dJ * dJ)[None, :]
    d1 = (lnFn - np.log(K)) / v + 0.5 * v
    d2 = d1 - v
    Fn = np.exp(lnFn)
    put = (K * ndtr(-d2) - Fn * ndtr(-d1)) @ wts
    call = (Fn * ndtr(d1) - K * ndtr(d2)) @ wts
    return np.where(k < 0, put, call)


def moments_from_prices(Q, pmin_over_F=0.0):
    k = KGRID
    if pmin_over_F > 0:
        lo = np.where((k < 0) & (Q < pmin_over_F))[0]
        hi = np.where((k > 0) & (Q < pmin_over_F))[0]
        mask = np.ones_like(k, bool)
        if len(lo):
            mask[: lo.max() + 1] = False
        if len(hi):
            mask[hi.min():] = False
        Q = np.where(mask, Q, 0.0)
    g = Q * np.exp(-k) * DK
    V = np.sum(2 * (1 - k) * g)
    W = np.sum((6 * k - 3 * k * k) * g)
    X = np.sum((12 * k * k - 4 * k ** 3) * g)
    mu = -V / 2 - W / 6 - X / 24
    var = V - mu * mu
    return 2 * np.sum(g), (W - 3 * mu * V + 2 * mu ** 3) / var ** 1.5


def merton_moments(T, sig, lam, muJ, dJ, pmin_over_F=0.0):
    return moments_from_prices(merton_otm_over_F(KGRID, T, sig, lam, muJ, dJ), pmin_over_F)


def merton_put(S, K, tau, r, q, sig, lam, muJ, dJ):
    """Model mid of a European put (index points)."""
    if tau <= 1e-6:
        return max(K - S, 0.0)
    F = S * math.exp((r - q) * tau)
    k = math.log(K / F)
    return math.exp(-r * tau) * F * float(merton_otm_over_F(np.array([k]), tau, sig, lam, muJ, dJ)[0])


def merton_sig_for_tenor(tau, tv_varswap, lam, muJ, dJ, floor=0.03):
    """Diffusion vol for tenor tau so model var-swap total variance matches the VIX term curve."""
    s2 = (tv_varswap - merton_jump_varswap_rate(lam, muJ, dJ) * tau) / tau
    return math.sqrt(max(s2, floor * floor))


# ---------------------------------------------------------------------------------------------
# BASE MODEL ("linear-z skew rule").  Normalised moneyness z = ln(K/F) / (sigma_a(T) * sqrt(T)).
#   put side  (z<0): IV = sigma_a(T) * (1 + beta_t * |z|^0.85)
#   call side (z>=0): IV = sigma_a(T) * (1 - 0.15 z + 0.06 z^2) up to z=3, then linear slope 0.21
#   IV capped at 300%.
# beta_t (one number per day, all tenors) and sigma_a(30d) are solved daily so that the model's
# CBOE-style 30-day variance equals VIX^2 and its CBOE-style skewness equals (100-SKEW)/10.
# sigma_a(T) for other tenors is solved so that model variance-swap total variance equals the
# VIX/VIX3M/VIX6M/VIX1Y curve (same beta).  The shape (exponent 0.85 = best of {0.8..1.05} on the chain, call side) was read off the
# 2026-09-22 SPX chain, where IV/ATM vs z coincides across 24-178 day expiries.
# ---------------------------------------------------------------------------------------------
PEXP = 0.85


def linz_iv(k, T, sa, beta):
    z = k / (sa * math.sqrt(T))
    zc = np.minimum(z, 3.0)
    gc = 1 - 0.15 * zc + 0.06 * zc * zc + 0.21 * np.maximum(z - 3.0, 0.0)
    g = np.where(z < 0, 1 + beta * np.abs(z) ** PEXP, gc)
    return np.minimum(sa * g, 3.0)


def linz_otm_over_F(k, T, sa, beta):
    iv = linz_iv(k, T, sa, beta)
    return bs_otm_over_F(k, iv * iv * T)


def linz_moments(T, sa, beta, pmin_over_F=0.0):
    return moments_from_prices(linz_otm_over_F(KGRID, T, sa, beta), pmin_over_F)


def linz_put(S, K, tau, r, q, sa, beta):
    if tau <= 1e-6:
        return max(K - S, 0.0)
    F = S * math.exp((r - q) * tau)
    k = math.log(K / F)
    z = k / (sa * math.sqrt(tau))
    if z < 0:
        g = 1 + beta * abs(z) ** PEXP
    else:
        zc = min(z, 3.0)
        g = 1 - 0.15 * zc + 0.06 * zc * zc + 0.21 * max(z - 3.0, 0.0)
    iv = min(sa * g, 3.0)
    sw = iv * math.sqrt(tau)
    d1 = -k / sw + 0.5 * sw
    d2 = d1 - sw
    return math.exp(-r * tau) * (K * _N(-d2) - F * _N(-d1))
