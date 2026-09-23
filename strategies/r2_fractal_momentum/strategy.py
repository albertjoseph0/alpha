"""r2:fractal_mom_joseph - 12-1 industry momentum on the 49 industries, measured on the
"Joseph" (continuous) part of each price path, with the "Noah" (jump) days winsorised.

Mandelbrot & Hudson, Misbehavior of Markets ch. X (Noah vs Joseph effects, extracted pp. ~225-234):
a price path mixes persistent drift (Joseph) with discontinuous jumps (Noah). In round 1 the jump part of
a 12-month move had no cross-sectional information. On the 49 industries its rank IC is again ~0
(and slightly negative given momentum). The winsorised part has a small positive incremental IC over plain
momentum in every period tested (see README.md).

Rule: on the first trading day of each month, for every i49 industry with >= 250 valid days in the last 252,
clip each daily log return to +-3 sigma, where sigma is the std of that industry's daily log returns over the
252 days ending the previous day. Sum the clipped returns over days t-251..t-21 (12-1 window). Hold the top third
equal-weighted, fully invested, and drift between rebalances.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

from harness import I49, MarketData, Strategy

LOOK, SKIP = 252, 21   # 12-1 momentum window
CLIP = 3.0             # jump threshold in trailing sigmas (conventional outlier cut, not tuned)
FRAC = 1 / 3           # top third of the available industries
MIN_VALID = 250        # valid daily observations required in the last 252 days


def _tsum(x: np.ndarray, w: int) -> np.ndarray:
    """Trailing sum over the w rows ending at t (prefix sums, so truncation-invariant)."""
    c = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    out = np.full(x.shape, np.nan)
    if len(x) >= w:
        out[w - 1:] = c[w:] - c[:-w]
    return out


def _lag(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    if k < len(x):
        out[k:] = x[:len(x) - k]
    return out


def joseph_momentum(r: np.ndarray) -> np.ndarray:
    """12-1 sum of daily log returns winsorised at +-CLIP x trailing sigma (sigma through t-1)."""
    s1, s2 = _tsum(r, LOOK), _tsum(r * r, LOOK)
    sig = _lag(np.sqrt(np.maximum((s2 - s1 * s1 / LOOK) / (LOOK - 1), 0.0)), 1)
    x = np.where(np.isnan(sig), r, np.clip(r, -CLIP * sig, CLIP * sig))
    return _lag(_tsum(x, LOOK - SKIP), SKIP)


class FractalMomJoseph(Strategy):
    name = "r2:fractal_mom_joseph"
    refit_every = None  # nothing is fitted

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.tradeable_returns()[I49]
        valid = (R.notna().rolling(LOOK).sum() >= MIN_VALID).to_numpy()
        r = np.log1p(R.fillna(0.0).to_numpy(dtype=np.float64))
        sig = np.where(valid, joseph_momentum(r), np.nan)

        cal = data.dates
        pos = cal.get_indexer(dates)
        prev_month = np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        rebalance = dates.month.to_numpy() != prev_month

        out = np.full((len(dates), len(I49)), np.nan)
        for i in np.where(rebalance)[0]:
            row = pd.Series(sig[pos[i]], index=I49).dropna()
            w = np.zeros(len(I49))
            if len(row):
                k = max(1, int(round(len(row) * FRAC)))
                top = row.nlargest(k).index
                w[[I49.index(c) for c in top]] = 1.0 / k
            out[i] = w
        return pd.DataFrame(out, index=dates, columns=I49)
