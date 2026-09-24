"""Validate the VIX/SKEW-calibrated skew model against the one real SPX chain we have
(CBOE delayed quotes, close of 2026-09-22).

1. Recompute VIX and SKEW from the chain with the CBOE method (checks our moment formulas).
2. Calibrate the SSVI model to that day's published VIX / VIX3M / VIX6M / VIX1Y / SKEW
   for rho in {-0.5, -0.7, -0.9} and compare model put prices / IVs with real bid/ask.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).parent))
from pricing import model_moments, put_price, put_iv, varswap_total_var  # noqa: E402

D = Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell"
OUT = Path(__file__).parent
DATE = pd.Timestamp("2026-09-22 16:15")


def load_chain():
    d = json.load(open(D / "spx_chain.json"))
    o = pd.DataFrame(d["data"]["options"])
    m = o.option.str.extract(r"^(SPXW?)(\d{6})([CP])(\d{8})$")
    o["root"], o["cp"] = m[0], m[2]
    o["exp"] = pd.to_datetime(m[1], format="%y%m%d")
    o["K"] = m[3].astype(float) / 1000
    # AM-settled SPX monthlies expire at the open, SPXW at 16:00
    o["texp"] = o["exp"] + pd.to_timedelta(np.where(o.root == "SPX", 9.5, 16.0), unit="h")
    o["T"] = (o["texp"] - DATE).dt.total_seconds() / (365 * 86400)
    o["mid"] = (o.bid + o.ask) / 2
    return o, d["data"]["current_price"]


def cboe_moments(ch, R):
    """CBOE VIX sigma^2 and SKEW S for one expiry (both roots merged, prefer root with more strikes)."""
    c = ch[ch.cp == "C"].set_index("K")
    p = ch[ch.cp == "P"].set_index("K")
    Ks = sorted(set(c.index) & set(p.index))
    diff = [(abs(c.loc[k, "mid"] - p.loc[k, "mid"]), k) for k in Ks if c.loc[k, "bid"] > 0 and p.loc[k, "bid"] > 0]
    kstar = min(diff)[1]
    T = ch["T"].iloc[0]
    F = kstar + math.exp(R * T) * (c.loc[kstar, "mid"] - p.loc[kstar, "mid"])
    K0 = max(k for k in Ks if k <= F)
    rows = []
    # puts below K0 going down, stop after two consecutive zero bids
    zeros = 0
    for k in sorted([k for k in p.index if k < K0], reverse=True):
        if p.loc[k, "bid"] <= 0:
            zeros += 1
            if zeros >= 2:
                break
            continue
        zeros = 0
        rows.append((k, p.loc[k, "mid"]))
    zeros = 0
    for k in sorted([k for k in c.index if k > K0]):
        if c.loc[k, "bid"] <= 0:
            zeros += 1
            if zeros >= 2:
                break
            continue
        zeros = 0
        rows.append((k, c.loc[k, "mid"]))
    rows.append((K0, 0.5 * (p.loc[K0, "mid"] + c.loc[K0, "mid"])))
    q = pd.Series(dict(rows)).sort_index()
    K = q.index.values
    dK = np.gradient(K)
    Q = q.values
    e = math.exp(R * T)
    sig2 = 2 / T * np.sum(dK / K ** 2 * e * Q) - 1 / T * (F / K0 - 1) ** 2
    l = np.log(K / F)
    lk0 = math.log(K0 / F)
    e1 = -(1 + math.log(F / K0) - F / K0)
    e2 = 2 * lk0 * (F / K0 - 1) + 0.5 * lk0 ** 2
    e3 = 3 * lk0 ** 2 * (lk0 / 3 - 1 + F / K0)
    P1 = e * (-np.sum(dK / K ** 2 * Q)) + e1
    P2 = e * np.sum(2 / K ** 2 * (1 - l) * Q * dK) + e2
    P3 = e * np.sum(3 / K ** 2 * (2 * l - l ** 2) * Q * dK) + e3
    S = (P3 - 3 * P1 * P2 + 2 * P1 ** 3) / (P2 - P1 ** 2) ** 1.5
    return T, F, sig2, S, K.min(), K.max()


def calibrate(vix, skew_idx, rho, S_level):
    T30 = 30 / 365
    target_s = (100 - skew_idx) / 10
    pmin = 0.05 / S_level

    def res(p):
        th, ps = math.exp(p[0]), math.exp(p[1])
        v2T, s = model_moments(th, ps, rho, pmin)
        return [math.log(v2T / (vix ** 2 * T30)) * 10, (s - target_s)]

    x0 = [math.log((0.8 * vix) ** 2 * T30), math.log(1.0)]
    sol = least_squares(res, x0, bounds=([-12, -4], [0, 2.5]))
    th, ps = math.exp(sol.x[0]), math.exp(sol.x[1])
    return th, ps, sol.fun


def main():
    o, S0 = load_chain()
    R = 0.037  # approx 3m T-bill yield on 2026-09-22 (IRX) ; only used for tiny discounting
    panel = pd.read_pickle(D / "panel.pkl")
    row = panel.loc["2026-09-22"]
    R = float(row["r"])
    print("spot", S0, "VIX", row.VIX, "VIX3M", row.VIX3M, "VIX6M", row.VIX6M, "VIX1Y", row.VIX1Y, "SKEW", row.SKEW, "r", R, "q", row.q)
    # --- 1. CBOE method on real chain
    res = []
    for e, ch in o.groupby("exp"):
        T = ch["T"].iloc[0]
        if not (15 / 365 < T < 50 / 365):
            continue
        # merge roots: prefer SPXW for PM expiries, SPX for 3rd-Friday AM
        roots = ch.root.unique()
        root = "SPX" if "SPX" in roots else "SPXW"
        sub = ch[ch.root == root]
        try:
            res.append((e.date(), root) + cboe_moments(sub, R))
        except Exception as ex:  # noqa
            print("fail", e, ex)
    r = pd.DataFrame(res, columns=["exp", "root", "T", "F", "sig2", "S", "Kmin", "Kmax"])
    r["days"] = r["T"] * 365
    r["vol"] = np.sqrt(r.sig2) * 100
    r["SKEWlike"] = 100 - 10 * r.S
    print(r.to_string())
    # interpolate to 30d
    near = r[r.days <= 30].iloc[-1]
    nxt = r[r.days > 30].iloc[0]
    w = (nxt.days - 30) / (nxt.days - near.days)
    vix_c = math.sqrt((w * near.sig2 * near["T"] + (1 - w) * nxt.sig2 * nxt["T"]) / (30 / 365)) * 100
    s_c = w * near.S + (1 - w) * nxt.S
    print(f"chain-implied VIX {vix_c:.2f} (published {row.VIX}), SKEW {100-10*s_c:.1f} (published {row.SKEW})")

    # --- 2. model vs chain for OTM puts
    puts = o[(o.cp == "P") & (o.root == "SPX") & (o.bid > 0)].copy()
    puts["mny"] = puts.K / S0 - 1
    puts = puts[puts.mny.between(-0.46, -0.04) & (puts["T"] < 0.85)]
    puts = puts[(puts.K % 100 == 0)]
    out = []
    for rho in [-0.5, -0.7, -0.9]:
        th, ps, fun = calibrate(row.VIX / 100, row.SKEW, rho, S0)
        v30 = row.VIX / 100
        tv30 = varswap_total_var(30 / 365, v30, row.VIX3M / 100, row.VIX6M / 100, row.VIX1Y / 100)
        ratio = th / tv30
        print(f"rho {rho}: theta30 {th:.6f} (ATM vol {math.sqrt(th/(30/365)):.4f}) psi {ps:.3f} resid {fun}")
        for _, p in puts.iterrows():
            tau = p["T"]
            thT = ratio * varswap_total_var(tau, v30, row.VIX3M / 100, row.VIX6M / 100, row.VIX1Y / 100)
            mp = put_price(S0, p.K, tau, R, row.q, thT, ps, rho)
            miv = put_iv(S0, p.K, tau, R, row.q, thT, ps, rho)
            out.append(dict(rho=rho, exp=p.exp.date(), days=round(tau * 365), mny=round(p.mny, 3), K=p.K,
                            bid=p.bid, ask=p.ask, mid=p.mid, model=mp, iv_chain=p.iv, iv_model=miv))
    df = pd.DataFrame(out)
    df["model/mid"] = df.model / df["mid"]
    df["spread/mid"] = (df.ask - df.bid) / df["mid"]
    df.to_csv(OUT / "chain_check.csv", index=False)
    # summary: bucket by moneyness and tenor
    df["mb"] = pd.cut(df.mny, [-0.47, -0.35, -0.25, -0.15, -0.04], labels=["35-46%", "25-35%", "15-25%", "4-15%"])
    df["tb"] = pd.cut(df.days, [0, 40, 70, 100, 200, 320], labels=["~1m", "~2m", "~3m", "4-6m", "7-10m"])
    piv = df.groupby(["rho", "mb", "tb"], observed=True)["model/mid"].median().unstack("tb")
    print("\nmedian model price / real mid:\n", piv.round(2).to_string())
    sp = df[df.rho == -0.7].groupby(["mb", "tb"], observed=True)["spread/mid"].median().unstack("tb")
    print("\nmedian real bid-ask spread / mid:\n", sp.round(3).to_string())


if __name__ == "__main__":
    main()
