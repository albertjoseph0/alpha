"""Daily surface parameters for the whole sample (1990-01-02 .. 2026-09-22).

For each day t (information known at the close of t):
  * VIX3M / VIX1Y missing before 2006-07 / 2007-01 -> proxy ln(VIXnM) = a + b ln(VIX), fitted on the
    DEV overlap only (<= 2007-12-31).  VIX6M missing before 2008 -> total-variance interpolation
    between the 91d and 365d points.
  * (sigma_a30, beta) solved to VIX and SKEW (base linear-z model, pricing.py).
  * sigma_a(T) on a tenor grid solved to the variance-swap curve.
Output: data/round5/m04_tail_barbell/surface.pkl
Run: python calibrate_surface.py [PEXP] [SKEW_WIN]   (PEXP variant for sensitivity, default 0.85;
     SKEW_WIN>1 calibrates to the trailing SKEW_WIN-day mean of SKEW (known at t), output surface_s<WIN>.pkl.
     Added in round 5b: the raw daily SKEW is noisy and makes 30%-OTM marks jump up to 100x in flat markets.)
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import pricing  # noqa: E402
from pricing import varswap_total_var  # noqa: E402
from linz_calib import calib30, sa_for_tenor  # noqa: E402

D = Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell"
TENORS_D = np.array([2, 7, 14, 21, 30, 45, 60, 75, 91, 120, 150, 182, 213])


def fit_proxy(df, col):
    ov = df[[col, "VIX"]].dropna()
    ov = ov[ov.index <= "2007-12-31"]
    x, y = np.log(ov.VIX.values), np.log(ov[col].values)
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)
    return a, b, len(ov), float(resid.std()), ov.index.min().date()


def main(pexp=0.85, skew_win=1):
    pricing.PEXP = pexp
    df = pd.read_pickle(D / "panel.pkl")
    df["SKEW_RAW"] = df["SKEW"]
    if skew_win > 1:
        df["SKEW"] = df["SKEW"].rolling(skew_win, min_periods=1).mean()
    proxies = {}
    for col in ["VIX3M", "VIX1Y"]:
        a, b, n, sd, start = fit_proxy(df, col)
        proxies[col] = (a, b, n, sd, str(start))
        est = np.exp(a + b * np.log(df.VIX))
        df[col + "_used"] = df[col].fillna(est)
        df[col + "_proxy"] = df[col].isna()
    print("dev-only proxies ln(X)=a+b ln(VIX):", proxies)
    tv91 = (df.VIX3M_used / 100) ** 2 * 91 / 365
    tv365 = (df.VIX1Y_used / 100) ** 2
    tv182 = tv91 + (182 - 91) / (365 - 91) * (tv365 - tv91)
    df["VIX6M_used"] = df.VIX6M.fillna(100 * np.sqrt(tv182 / (182 / 365)))
    out = []
    x0 = None
    for i, (dt, r) in enumerate(df.iterrows()):
        v = [r.VIX / 100, r.VIX3M_used / 100, r.VIX6M_used / 100, r.VIX1Y_used / 100]
        sa, beta, err, x = calib30(v[0], r.SKEW, r.SPX, x0)
        if err > 1e-4:  # retry from the default start
            sa2, beta2, err2, x2 = calib30(v[0], r.SKEW, r.SPX, None)
            if err2 < err:
                sa, beta, err, x = sa2, beta2, err2, x2
        x0 = list(x)
        rec = dict(date=dt, sa30=sa, beta=beta, calib_err=err)
        for td in TENORS_D:
            T = td / 365
            rec[f"sa_{td}"] = sa_for_tenor(T, varswap_total_var(T, *v), beta, r.SPX, sa)
        out.append(rec)
        if i % 1000 == 0:
            print(dt.date(), rec["sa30"], rec["beta"], err, flush=True)
    s = pd.DataFrame(out).set_index("date")
    s = s.join(df[["SPX", "VIX", "SKEW", "r", "q", "VIX3M_used", "VIX6M_used", "VIX1Y_used", "VIX3M_proxy"]])
    tag = ("" if abs(pexp - 0.85) < 1e-9 else f"_p{pexp}") + (f"_s{skew_win}" if skew_win > 1 else "")
    s.to_pickle(D / f"surface{tag}.pkl")
    print(s.describe().T.round(4).to_string())
    print("days with calib_err>1e-3:", int((s.calib_err > 1e-3).sum()))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.85, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
