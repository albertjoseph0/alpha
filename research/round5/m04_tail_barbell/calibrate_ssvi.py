"""Daily SSVI (rho=-0.7) calibration: the expensive-pricing sensitivity case.

Same inputs as calibrate_surface.py (VIX, SKEW, and the VIX3M/VIX6M/VIX1Y curve with dev-only proxies).
theta30, psi are solved so the model's CBOE-style 30d variance = VIX^2 and skewness = (100-SKEW)/10.
Other tenors: theta_T = (theta30 / varswap_tv(30d)) * varswap_tv(T), psi constant (as in chain_check.py).
On the 2026-09-22 chain this model priced 5-46% OTM puts at 1.3-1.7x the real mid.
Output: data/round5/m04_tail_barbell/surface_ssvi.pkl  (needs surface.pkl for the tenor curve)
Run: python calibrate_ssvi.py [SKEW_WIN]  -> with SKEW_WIN>1 reads surface_s<WIN>.pkl (SKEW already smoothed)
     and writes surface_ssvi_s<WIN>.pkl
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).parent))
from pricing import model_moments, varswap_total_var  # noqa: E402

D = Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell"
RHO = -0.7
T30 = 30 / 365


def calib(vix, skew_idx, S_level, x0):
    target_s = (100 - skew_idx) / 10
    pmin = 0.05 / S_level

    def res(p):
        v2T, s = model_moments(math.exp(p[0]), math.exp(p[1]), RHO, pmin)
        return [math.log(v2T / (vix ** 2 * T30)) * 10, s - target_s]

    sol = least_squares(res, x0, bounds=([-12, -4], [0, 2.5]), xtol=1e-10, ftol=1e-10)
    return sol.x, float(np.abs(sol.fun).max())


def main(win=1):
    tag = f"_s{win}" if win > 1 else ""
    s = pd.read_pickle(D / f"surface{tag}.pkl")
    out = []
    x0 = None
    for i, (dt, r) in enumerate(s.iterrows()):
        v = [r.VIX / 100, r.VIX3M_used / 100, r.VIX6M_used / 100, r.VIX1Y_used / 100]
        d0 = [math.log((0.8 * v[0]) ** 2 * T30), 0.0]
        x, err = calib(v[0], r.SKEW, r.SPX, x0 if x0 is not None else d0)
        if err > 1e-4:
            x2, err2 = calib(v[0], r.SKEW, r.SPX, d0)
            if err2 < err:
                x, err = x2, err2
        x0 = list(x)
        th = math.exp(x[0])
        out.append(dict(date=dt, theta30=th, psi=math.exp(x[1]), ratio=th / varswap_total_var(T30, *v),
                        ssvi_err=err))
        if i % 1000 == 0:
            print(dt.date(), out[-1], flush=True)
    o = pd.DataFrame(out).set_index("date")
    o.to_pickle(D / f"surface_ssvi{tag}.pkl")
    print(o.describe().T.round(4).to_string())
    print("days with err>1e-3:", int((o.ssvi_err > 1e-3).sum()))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
