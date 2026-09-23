"""fractal:mfvol_ttmom_kelly -- industry momentum in multifractal trading time,
sized by a growth-optimal (Kelly) cap on MRW volatility forecasts.

1. For each of the 12 industries, forecast the variance of the next 21 traded
   days with the Multifractal Random Walk optimal linear predictor (Borland et
   al. eqs. 10-12): log-vol covariance lambda^2 ln(T/(tau+1)); lambda^2 and T
   are fitted at each annual refit from the log-covariance of log|r|, and the
   Toeplitz-solved predictor weights are applied to the last 1000 log|r|.
2. Trading time (Mandelbrot ch. XI, heresy 5): dtheta = forecast daily
   variance. Momentum score = sum of log returns over [t-251, t-21] divided by
   sqrt(elapsed trading time) over the same window (a z-score in trading time).
3. On the first trading day of each month hold the top 4 industries, 1/4 each,
   each capped at its Kelly fraction mu / sigma^2 (mu = long-run market excess
   return, sigma^2 = MRW forecast); the remainder earns T-bills (heresy 9).
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mfvol as mv  # noqa: E402

from harness import INDUSTRIES, MarketData, Strategy  # noqa: E402

H = 21          # forecast horizon (days)
L = 1000        # MRW predictor length (days)
LOOKBACK = 252  # momentum window (days)
SKIP = 21       # skip the most recent month
TOP_K = 4


def _mrw_params(lr: np.ndarray) -> dict:
    ttr = mv.fwd_rv(lr, H)
    y = mv.logabs(lr)
    lam2, T = mv.mrw_logcov_fit(y)
    T = float(np.clip(T, 60, 5000))
    w = mv.mrw_weights(lam2, T, L, H)
    mu = float(y.mean())
    s = mv.mrw_signal(y, w, mu)
    ok = np.isfinite(ttr) & np.isfinite(s)
    c = float(np.log(np.mean(ttr[ok] / np.exp(2 * s[ok]))))
    return {"w": w, "mu": mu, "c": c, "lam2": lam2, "T": T}


class MultifractalTradingTimeMomentum(Strategy):
    name = "fractal:mfvol_ttmom_kelly"
    refit_every = 252

    def fit(self, data: MarketData) -> None:
        lr = data.log_returns()
        self.params = {a: _mrw_params(lr[a].to_numpy()) for a in INDUSTRIES}
        ex = data.returns["Mkt"] - data.rf
        self.mu_excess = max(float(ex.mean() * 252), 0.0)

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        cal = data.dates
        pos = cal.get_indexer(dates)
        # only the history needed: MRW filter (L) + momentum window
        start = max(0, int(pos.min()) - (L + LOOKBACK + 5))
        lr = data.log_returns().iloc[start:]
        n = len(lr)
        fc = np.full((n, len(INDUSTRIES)), np.nan)
        for j, a in enumerate(INDUSTRIES):
            p = self.params[a]
            s = mv.mrw_signal(mv.logabs(lr[a].to_numpy()), p["w"], p["mu"])
            fc[:, j] = np.exp(p["c"] + 2 * s)
        fc = pd.DataFrame(fc, index=lr.index, columns=INDUSTRIES)
        win = LOOKBACK - SKIP
        num = lr[INDUSTRIES].rolling(win).sum().shift(SKIP)
        den = (fc / H).shift(1).rolling(win).sum().shift(SKIP)
        score = (num / np.sqrt(den)).reindex(dates)
        var_ann = (fc * 252 / H).reindex(dates)

        prev_month = np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        rebal = dates.month != prev_month
        out = pd.DataFrame(np.nan, index=dates, columns=INDUSTRIES)
        for i, d in enumerate(dates):
            if not rebal[i]:
                continue
            sc = score.loc[d]
            row = pd.Series(0.0, index=INDUSTRIES)
            if sc.notna().sum() >= TOP_K:
                top = sc.dropna().sort_values(ascending=False, kind="mergesort").index[:TOP_K]
                kelly = np.clip(self.mu_excess / var_ann.loc[d, top], 0.0, 1.0)
                row[top] = kelly / TOP_K
            out.loc[d] = row.to_numpy()
        return out
