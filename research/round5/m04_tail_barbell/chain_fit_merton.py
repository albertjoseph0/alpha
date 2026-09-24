"""Choose the two structural jump constants (muJ, dJ) of the Merton variant on the one real
SPX chain (2026-09-22 close), then report model/real price ratios by moneyness and tenor.
Daily sigma and lambda are always solved from VIX and SKEW; only muJ, dJ are fitted here.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).parent))
from pricing import merton_moments, merton_put, merton_sig_for_tenor, varswap_total_var  # noqa: E402
from chain_check import load_chain, D  # noqa: E402

OUT = Path(__file__).parent
T30 = 30 / 365


def calibrate_merton(vix, skew_idx, muJ, dJ, S_level, x0=None):
    target = (100 - skew_idx) / 10
    pmin = 0.05 / S_level

    def res(p):
        sig, lam = math.exp(p[0]), math.exp(p[1])
        v2T, s = merton_moments(T30, sig, lam, muJ, dJ, pmin)
        return [math.log(v2T / (vix ** 2 * T30)) * 10, s - target]

    x0 = x0 if x0 is not None else [math.log(0.7 * vix), math.log(0.5)]
    sol = least_squares(res, x0, bounds=([math.log(0.01), math.log(1e-4)], [math.log(3.0), math.log(200)]))
    return math.exp(sol.x[0]), math.exp(sol.x[1]), float(np.abs(sol.fun).max()), sol.x


def main():
    o, S0 = load_chain()
    panel = pd.read_pickle(D / "panel.pkl")
    row = panel.loc["2026-09-22"]
    R, q = float(row["r"]), float(row["q"])
    vs = [row.VIX / 100, row.VIX3M / 100, row.VIX6M / 100, row.VIX1Y / 100]
    puts = o[(o.cp == "P") & (o.root == "SPX") & (o.bid > 0)].copy()
    puts["mny"] = puts.K / S0 - 1
    puts = puts[puts.mny.between(-0.46, -0.04) & (puts["T"] < 0.55) & (puts.K % 100 == 0)]
    puts = puts[puts["T"] > 40 / 365]  # the strategy only buys 2-6 month puts; 1m checked separately
    rows = []
    for muJ in [-0.04, -0.07, -0.10, -0.14, -0.18, -0.25]:
        for dJ in [0.03, 0.06, 0.10, 0.15]:
            sig, lam, err, _ = calibrate_merton(vs[0], row.SKEW, muJ, dJ, S0)
            if err > 1e-3:
                rows.append(dict(muJ=muJ, dJ=dJ, sig=sig, lam=lam, fit_err=err, rmse=np.nan))
                continue
            lr = []
            for _, p in puts.iterrows():
                tau = p["T"]
                tv = varswap_total_var(tau, *vs)
                s_t = merton_sig_for_tenor(tau, tv, lam, muJ, dJ)
                mp = merton_put(S0, p.K, tau, R, q, s_t, lam, muJ, dJ)
                lr.append(math.log(mp / p["mid"]))
            lr = np.array(lr)
            rows.append(dict(muJ=muJ, dJ=dJ, sig=sig, lam=lam, fit_err=err, rmse=np.sqrt(np.mean(lr ** 2)),
                             bias=np.mean(lr)))
    g = pd.DataFrame(rows).sort_values("rmse")
    print(g.round(4).to_string(index=False))
    g.to_csv(OUT / "chain_fit_merton_grid.csv", index=False)
    best = g.iloc[0]
    muJ, dJ = best.muJ, best.dJ
    sig, lam, _, _ = calibrate_merton(vs[0], row.SKEW, muJ, dJ, S0)
    allp = o[(o.cp == "P") & (o.root == "SPX") & (o.bid > 0)].copy()
    allp["mny"] = allp.K / S0 - 1
    allp = allp[allp.mny.between(-0.46, -0.04) & (allp["T"] < 0.85) & (allp.K % 100 == 0)]
    out = []
    for _, p in allp.iterrows():
        tau = p["T"]
        tv = varswap_total_var(tau, *vs)
        s_t = merton_sig_for_tenor(tau, tv, lam, muJ, dJ)
        mp = merton_put(S0, p.K, tau, R, q, s_t, lam, muJ, dJ)
        out.append(dict(days=round(tau * 365), mny=p.mny, bid=p.bid, ask=p.ask, mid=p["mid"], model=mp))
    df = pd.DataFrame(out)
    df["model/mid"] = df.model / df["mid"]
    df["mb"] = pd.cut(df.mny, [-0.47, -0.35, -0.25, -0.15, -0.04], labels=["35-46%", "25-35%", "15-25%", "4-15%"])
    df["tb"] = pd.cut(df.days, [0, 40, 70, 100, 200, 320], labels=["~1m", "~2m", "~3m", "4-6m", "7-10m"])
    print(f"\nbest muJ={muJ} dJ={dJ}: sigma30={sig:.4f} lambda={lam:.3f}/yr")
    print("median model/real-mid (Merton):\n", df.groupby(["mb", "tb"], observed=True)["model/mid"].median().unstack().round(2).to_string())
    df.to_csv(OUT / "chain_check_merton.csv", index=False)


if __name__ == "__main__":
    main()
