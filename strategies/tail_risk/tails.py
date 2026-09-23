"""Tail-risk toolkit for the fractal:tails_ strategy.

Pure numpy / scipy functions, no state. Everything is computed from a trailing window
passed in by the caller, so results depend only on data up to the decision date.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog


def hill_alpha(x: np.ndarray, frac: float = 0.05) -> float:
    """Hill estimator of the tail exponent of the positive part of x (largest frac of obs).

    Mandelbrot's alpha (book ch. VIII, p. 163) / Borland et al.'s mu (p. 4).
    Pass -r for the left (loss) tail.
    """
    x = np.sort(x[np.isfinite(x)])[::-1]
    k = max(5, int(frac * len(x)))
    if len(x) <= k or x[k] <= 0:
        return np.nan
    return float(1.0 / np.mean(np.log(x[:k] / x[k])))


def cvar(port: np.ndarray, beta: float = 0.95) -> float:
    """Empirical expected shortfall (positive number = loss) of a return series."""
    p = np.sort(port)
    k = max(1, int(round((1 - beta) * len(p))))
    return float(-p[:k].mean())


def _cvar_lp_parts(X: np.ndarray, beta: float):
    T, n = X.shape
    # variables: w (n), a (1), u (T);  u_t >= -X_t w - a, u_t >= 0
    A_u = sp.hstack([sp.csr_matrix(-X), sp.csr_matrix(-np.ones((T, 1))), -sp.eye(T)]).tocsr()
    cv_row = np.concatenate([np.zeros(n), [1.0], np.full(T, 1.0 / ((1 - beta) * T))])
    return T, n, A_u, cv_row


def min_cvar_weights(X: np.ndarray, beta: float = 0.95, wmax: float = 1.0) -> np.ndarray:
    """Long-only fully invested portfolio minimising CVaR_beta (Rockafellar-Uryasev LP)."""
    T, n, A_u, cv_row = _cvar_lp_parts(X, beta)
    Aeq = np.concatenate([np.ones(n), [0.0], np.zeros(T)])[None, :]
    bounds = [(0, wmax)] * n + [(None, None)] + [(0, None)] * T
    res = linprog(cv_row, A_ub=A_u, b_ub=np.zeros(T), A_eq=Aeq, b_eq=[1.0],
                  bounds=bounds, method="highs")
    if not res.success:
        return np.full(n, 1.0 / n)
    return res.x[:n]


def frontier_weights(X: np.ndarray, score: np.ndarray, cvar_cap: float, beta: float = 0.95,
                     wmax: float = 0.25) -> np.ndarray:
    """Generalized efficiency frontier (Bouchaud et al. 1998 'tail chiseling', book p. 260).

    maximise score'w  s.t.  CVaR_beta(X w) <= cvar_cap,  sum w = 1,  0 <= w <= wmax.
    If the cap is infeasible, it is relaxed to the minimum attainable CVaR (+1%).
    """
    T, n, A_u, cv_row = _cvar_lp_parts(X, beta)
    Aeq = np.concatenate([np.ones(n), [0.0], np.zeros(T)])[None, :]
    bounds = [(0, wmax)] * n + [(None, None)] + [(0, None)] * T
    wmin = min_cvar_weights(X, beta, wmax)
    cmin = cvar(X @ wmin, beta)
    cap = max(min(cvar_cap, 1.0), cmin * 1.01)
    A = sp.vstack([A_u, sp.csr_matrix(cv_row[None, :])]).tocsr()
    b = np.concatenate([np.zeros(T), [cap]])
    c = np.concatenate([-score, [0.0], np.zeros(T)])
    res = linprog(c, A_ub=A, b_ub=b, A_eq=Aeq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        return wmin
    w = np.clip(res.x[:n], 0, None)
    return w / w.sum()
