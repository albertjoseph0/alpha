"""Market timing overlays built from tail / shock measures (Mkt as the risky asset).

All signals are causal (rolling). Decisions daily; weight rounding to reduce turnover.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
import pandas as pd
from bt import data, score, fmt
from harness import INDUSTRIES, ASSETS

d = data()
R = d.returns
m = R["Mkt"]
I = R[INDUSTRIES]
dates = R.index
ann = np.sqrt(252)


def ewvol(x, hl):
    return np.sqrt((x ** 2).ewm(halflife=hl, min_periods=hl).mean())


# multi-scale vol forecast (average of variances at several half-lives, a cheap HAR/MS proxy)
var_ms = sum(ewvol(m, h) ** 2 for h in (5, 21, 63, 250)) / 4
sig_ms = np.sqrt(var_ms) * ann


def panel(f, asset="Mkt", step=0.1):
    f = f.clip(0, 1)
    f = (f / step).round() * step  # discretise to limit turnover
    W = pd.DataFrame(0.0, index=dates, columns=ASSETS)
    W[asset] = f
    return W


def kelly_const(mu0=0.06):
    return mu0 / sig_ms ** 2


def kelly_fhs(mu0=0.06, win=1000):
    """Growth-optimal fraction with fat-tailed standardised residuals (filtered historical sim).

    f* = argmax_f mean(log(1 + f * (mu0/252 + s_t * z))) over trailing standardised residuals z.
    """
    s = np.sqrt(var_ms)  # daily
    z = (m / s.shift(1)).to_numpy()
    sv = s.to_numpy()
    grid = np.linspace(0, 1, 21)
    out = np.full(len(m), np.nan)
    for i in range(win + 300, len(m)):
        if i % 5 and not np.isnan(out[i - 1]):
            out[i] = out[i - 1]
            continue
        zz = z[i - win + 1:i + 1]
        zz = zz[np.isfinite(zz)]
        zz = zz - zz.mean()
        # 2-day holding (lag) -> scale by sqrt(2)? keep daily
        r = mu0 / 252 + sv[i] * zz
        g = [np.mean(np.log1p(f * r)) for f in grid]
        out[i] = grid[int(np.argmax(g))]
    return pd.Series(out, index=m.index)


def shock_index():
    base = m.rolling(1260, min_periods=500).std()
    scales = [m.rolling(h).std() for h in (5, 21, 63)]
    return sum(np.log2(v / base) for v in scales) / len(scales)


def cocrash(win=21):
    zi = I / I.rolling(252).std().shift(1)
    cc = ((zi < -2).sum(axis=1) >= 9).astype(float)
    return cc.rolling(win).sum()


exps = {}
exps["bh"] = lambda: pd.Series(1.0, index=dates)
exps["kelly_const6"] = lambda: kelly_const(0.06)
exps["kelly_fhs6"] = lambda: kelly_fhs(0.06)
exps["shock_gt1_half"] = lambda: pd.Series(np.where(shock_index() > 1.0, 0.5, 1.0), index=dates)
exps["cocrash21_ge2_half"] = lambda: pd.Series(np.where(cocrash() >= 2, 0.5, 1.0), index=dates)

which = sys.argv[1:] or list(exps)
for name in which:
    f = exps[name]().fillna(1.0)
    W = panel(f)
    o = score(W, "timing:" + name)
    print(f"{name:22s} {fmt(o)}  avg f {f.loc['1950':].clip(0,1).mean():.2f}  frac<1 {(f.loc['1950':]<0.95).mean():.2f}")
