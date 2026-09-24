"""Base (linear-z) model vs the real 2026-09-22 SPX chain. sigma_a and beta come ONLY from the
published VIX / VIX3M / VIX6M / VIX1Y / SKEW closes of that day, not from the chain."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from pricing import linz_put, varswap_total_var  # noqa: E402
from linz_calib import calib30, sa_for_tenor  # noqa: E402
from chain_check import load_chain, D  # noqa: E402

OUT = Path(__file__).parent


def main():
    o, S0 = load_chain()
    row = pd.read_pickle(D / "panel.pkl").loc["2026-09-22"]
    R, q = float(row["r"]), float(row["q"])
    vs = [row.VIX / 100, row.VIX3M / 100, row.VIX6M / 100, row.VIX1Y / 100]
    sa, beta, err, _ = calib30(vs[0], row.SKEW, S0)
    print(f"calibrated: sigma_a30={sa:.4f} beta={beta:.3f} resid={err:.2e}")
    p = o[(o.cp == "P") & (o.root == "SPX") & (o.bid > 0)].copy()
    p["mny"] = p.K / S0 - 1
    p = p[p.mny.between(-0.46, -0.04) & (p["T"] < 0.85) & (p.K % 100 == 0)]
    cache = {}
    out = []
    for _, x in p.iterrows():
        tau = x["T"]
        if tau not in cache:
            cache[tau] = sa_for_tenor(tau, varswap_total_var(tau, *vs), beta, S0, sa)
        mp = linz_put(S0, x.K, tau, R, q, cache[tau], beta)
        out.append(dict(days=round(tau * 365), mny=x.mny, bid=x.bid, ask=x.ask, mid=x["mid"], model=mp,
                        sa_T=cache[tau]))
    df = pd.DataFrame(out)
    df["model/mid"] = df.model / df["mid"]
    df["spread/mid"] = (df.ask - df.bid) / df["mid"]
    df["mb"] = pd.cut(df.mny, [-0.47, -0.35, -0.25, -0.15, -0.04], labels=["35-46%", "25-35%", "15-25%", "4-15%"])
    df["tb"] = pd.cut(df.days, [0, 40, 70, 100, 200, 320], labels=["~1m", "~2m", "~3m", "4-6m", "7-10m"])
    print("ATM sigma_a by tenor:", df.groupby("days").sa_T.first().round(4).to_dict())
    print("median model/real mid (linear-z base):\n",
          df.groupby(["mb", "tb"], observed=True)["model/mid"].median().unstack().round(2).to_string())
    print("share of model prices inside real [bid, ask]:",
          round(((df.model >= df.bid) & (df.model <= df.ask)).mean(), 3))
    print("median real spread/mid:\n", df.groupby(["mb", "tb"], observed=True)["spread/mid"].median().unstack().round(3).to_string())
    df.to_csv(OUT / "chain_check_linz.csv", index=False)


if __name__ == "__main__":
    main()
