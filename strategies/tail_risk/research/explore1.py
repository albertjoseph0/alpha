"""Descriptive tail statistics on dev data (1926-1999). Not a strategy evaluation."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np
import pandas as pd
from bt import data
from harness import INDUSTRIES

d = data()
R = d.returns
rf = d.rf
m = R["Mkt"]


def hill(x, k):
    """Hill estimator of the tail exponent of the positive values of x (largest k)."""
    x = np.sort(x[x > 0])[::-1]
    if len(x) <= k:
        return np.nan
    return 1.0 / np.mean(np.log(x[:k] / x[k]))


print("== Hill tail exponent (left tail = -r) of Mkt daily returns, k = 5% of obs ==")
for dec in range(1930, 2000, 10):
    x = m.loc[str(dec):str(dec + 9)].to_numpy()
    k = int(0.05 * len(x))
    print(dec, "left", round(hill(-x, k), 2), "right", round(hill(x, k), 2))

# vol-standardised residuals (EWMA vol, halflife 20d, lagged)
sig = np.sqrt((m ** 2).ewm(halflife=20, min_periods=60).mean().shift(1))
z = (m / sig).dropna()
print("== Hill on EWMA-standardised residuals (full 1927-99) ==")
for q in (0.02, 0.05, 0.1):
    k = int(q * len(z))
    print(q, "left", round(hill(-z.to_numpy(), k), 2), "right", round(hill(z.to_numpy(), k), 2))
x = m.to_numpy()
for q in (0.01, 0.02, 0.05):
    k = int(q * len(x))
    print("raw", q, "left", round(hill(-x, k), 2), "right", round(hill(x, k), 2))

# Concentration (heresy 3): share of log growth from best/worst 10 days per decade
print("== concentration: sum of 10 best / 10 worst daily log returns per decade vs decade total ==")
lm = np.log1p(m)
for dec in range(1950, 2000, 10):
    s = lm.loc[str(dec):str(dec + 9)]
    print(dec, "total", round(s.sum(), 3), "best10", round(s.nlargest(10).sum(), 3),
          "worst10", round(s.nsmallest(10).sum(), 3))

# Are best days in turbulent periods? vol percentile at time of best/worst 1% days
v63 = m.rolling(63).std()
vr = v63.rank(pct=True)
dev = m.loc["1950":]
best = dev.nlargest(int(0.01 * len(dev))).index
worst = dev.nsmallest(int(0.01 * len(dev))).index
print("median vol pct (63d, lagged 1) on best 1% days:", round(vr.shift(1).loc[best].median(), 2),
      " worst 1% days:", round(vr.shift(1).loc[worst].median(), 2))
