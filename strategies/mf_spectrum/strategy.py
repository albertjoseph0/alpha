"""fractal:mfspec_ruler_rotation - industry rotation on the signed ruler (divider) roughness
of each industry's 1-year price path.

Mandelbrot's ruler method (Misbehaviour of Markets, ch. VII, PDF pp.157-159; Notes pp.320-321):
the measured length of a rough curve grows as the ruler shrinks, L(eps) ~ eps^(1-D). For a
price path over a window of n days, the ratio L(n) / L(5 days) = |X| / L(5d) = (n/5)^(1-D)
is the path's "trend efficiency": close to 1 for a smooth trend (D -> 1), small for a
rough, space-filling path (D -> 2). Signed by the direction of the move, it ranks industries
by how smooth (Joseph-like) their trend is. A 5-day ruler is used instead of 1 day so the
estimate is not dominated by stale-price / microstructure autocorrelation (Bouchaud 2026 p.5;
research/REVIEW.md section 5).

Each month (first trading day), hold the 4 of 12 industries with the highest signed
efficiency, equally weighted, fully invested. See README.md: the multifractal-spectrum signals
(lambda^2, zeta_q curvature, local Hoelder exponent) were tested as timing/concentration filters
and did not add information beyond realized volatility, so they are not part of the final rule.
"""
import numpy as np
import pandas as pd

from harness import MarketData, Strategy
from harness.data import ASSETS, INDUSTRIES

WINDOW = 250   # outer ruler: ~1 year (multiple of the inner ruler)
RULER = 5      # inner ruler: 1 week
TOP_K = 4      # one third of the 12 industries


def _trailing_sum(x: np.ndarray, w: int) -> np.ndarray:
    """sum of x[t-w+1..t] along axis 0 via prefix sums (identical for any truncation after t)."""
    c = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    out = np.full(x.shape, np.nan)
    if len(x) >= w:
        out[w - 1:] = c[w:] - c[:-w]
    return out


def signed_efficiency(r: np.ndarray) -> np.ndarray:
    """X_WINDOW / L(RULER): displacement over path length measured with a RULER-day ruler
    (averaged over the RULER phases)."""
    X = _trailing_sum(r, WINDOW)
    step = np.abs(_trailing_sum(r, RULER))
    step[np.isnan(step)] = 0.0
    L = _trailing_sum(step, WINDOW - RULER + 1) / RULER
    L[: WINDOW - 1] = np.nan
    return X / L


class MFSpecRulerRotation(Strategy):
    name = "fractal:mfspec_ruler_rotation"
    refit_every = None  # nothing is fitted

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = np.log1p(data.returns[INDUSTRIES].to_numpy(dtype=np.float64))
        eff = pd.DataFrame(signed_efficiency(R), index=data.dates, columns=INDUSTRIES)
        full_idx = data.dates
        pos = full_idx.get_indexer(dates)
        prev_month = np.where(pos > 0, full_idx[np.maximum(pos - 1, 0)].month, -1)
        rebalance = dates.month.to_numpy() != prev_month

        e = eff.iloc[pos].to_numpy()
        out = np.full((len(dates), len(ASSETS)), np.nan)
        cols = [ASSETS.index(a) for a in INDUSTRIES]
        for i in range(len(dates)):
            if not rebalance[i]:
                continue  # hold / drift between monthly rebalances
            w = np.zeros(len(ASSETS))
            row = e[i]
            if np.isnan(row).any():
                w[cols] = 1.0 / len(INDUSTRIES)
            else:
                order = np.argsort(-row, kind="stable")[:TOP_K]
                w[np.array(cols)[order]] = 1.0 / TOP_K
            out[i] = w
        return pd.DataFrame(out, index=dates, columns=ASSETS)
