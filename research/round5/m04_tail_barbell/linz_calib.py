"""Daily calibration helpers for the linear-z base model."""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares

sys.path.insert(0, str(Path(__file__).parent))
from pricing import linz_moments  # noqa: E402

T30 = 30 / 365


def calib30(vix, skew_idx, S_level, x0=None):
    """Solve (sigma_a30, beta) so model VIX and SKEW match. Returns sa, beta, max abs residual."""
    target = (100 - skew_idx) / 10
    pmin = 0.05 / S_level

    def res(p):
        sa, beta = math.exp(p[0]), math.exp(p[1])
        v2T, s = linz_moments(T30, sa, beta, pmin)
        return [math.log(v2T / (vix ** 2 * T30)) * 10, s - target]

    x0 = x0 if x0 is not None else [math.log(0.75 * vix), math.log(0.25)]
    sol = least_squares(res, x0, bounds=([math.log(0.01), math.log(0.005)], [math.log(3.0), math.log(3.0)]),
                        xtol=1e-10, ftol=1e-10)
    return math.exp(sol.x[0]), math.exp(sol.x[1]), float(np.abs(sol.fun).max()), sol.x


def sa_for_tenor(T, tv_target, beta, S_level, sa_guess):
    """sigma_a(T) such that model var-swap total variance at T equals tv_target."""
    pmin = 0.05 / S_level

    def f(ls):
        v2T, _ = linz_moments(T, math.exp(ls), beta, pmin)
        return math.log(v2T / tv_target)

    lo, hi = math.log(sa_guess) - 1.5, math.log(sa_guess) + 1.5
    try:
        return math.exp(brentq(f, lo, hi, xtol=1e-6))
    except ValueError:
        return sa_guess * math.sqrt(tv_target / (sa_guess ** 2 * T) + 1e-12)
