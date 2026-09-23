"""Forward Monte Carlo for deep:trend_switch_ens vs SPY.

Stationary block bootstrap of *paired* daily returns (strategy, SPY), so cross-correlation, volatility
clustering and fat tails inside each block are preserved. Mean block length is 3 months (geometric).
Source history: ETF START-2026 (research/deep/equity_2000_2026.csv, costs included).
"""
import sys

import numpy as np
import pandas as pd

START = sys.argv[1] if len(sys.argv) > 1 else "2000-01-01"   # e.g. 2008-01-01 for the recent, thin-edge regime

eq = pd.read_csv("research/deep/equity_2000_2026.csv", index_col=0, parse_dates=True).loc[START:]
R = np.log1p(eq.pct_change().dropna().to_numpy())      # columns: strategy, SPY
T = len(R); rng = np.random.default_rng(42); N = 10000; MEAN_BLOCK = 63


def sample_path(days):
    idx = np.empty(days, dtype=int); i = 0
    while i < days:
        start = rng.integers(0, T); L = rng.geometric(1 / MEAN_BLOCK)
        take = min(L, days - i); idx[i:i + take] = (start + np.arange(take)) % T; i += take
    return R[idx]


rows = []
for years in (1, 3, 5, 10, 20):
    days = 252 * years
    cagr = np.empty((N, 2)); mdd = np.empty((N, 2))
    for n in range(N):
        p = sample_path(days)
        cum = np.cumsum(p, axis=0)
        cagr[n] = np.expm1(cum[-1] / years)
        mdd[n] = np.expm1((cum - np.maximum.accumulate(np.vstack([np.zeros(2), cum]), axis=0)[1:]).min(axis=0))
    s, b = cagr[:, 0], cagr[:, 1]
    rows.append({
        "horizon_y": years,
        "strat_CAGR_p10": np.percentile(s, 10), "strat_CAGR_median": np.median(s),
        "strat_CAGR_p90": np.percentile(s, 90),
        "SPY_CAGR_median": np.median(b),
        "P(beat SPY)": (s > b).mean(),
        "P(strat loses money)": (s < 0).mean(), "P(SPY loses money)": (b < 0).mean(),
        "strat_maxDD_median": np.median(mdd[:, 0]), "strat_maxDD_p10(worst)": np.percentile(mdd[:, 0], 10),
        "SPY_maxDD_p10(worst)": np.percentile(mdd[:, 1], 10),
        "P(strat drawdown worse than -40%)": (mdd[:, 0] < -0.40).mean(),
        "P(SPY drawdown worse than -40%)": (mdd[:, 1] < -0.40).mean(),
    })
out = pd.DataFrame(rows).set_index("horizon_y")
out.to_csv(f"research/deep/monte_carlo_{START[:4]}.csv")
pd.set_option("display.width", 200)
print((out * 100).round(1).T.to_string())
