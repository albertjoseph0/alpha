"""DEV-only grid (1990-01-02 -> 2007-12-31). Every configuration and every cost case is logged.

Free parameters (2 x 2 x 3 x 2 = 24 configurations):
  depth   {0.20, 0.30}        strike = S (1 - depth)
  tenor   {2, 4}              expiry = 3rd Friday of month m+tenor (about 2.5 / 4.5 months at purchase)
  budget  {0.01, 0.02, 0.033} annual gross premium outlay as a fraction of NAV (budget/12 each month)
  monet   {None, 5}           early monetisation when the tranche mark >= 5x its cost (1-day lag)
Cost / pricing cases for every configuration:
  base    linz model on the smoothed-SKEW surface (_s21), half-spread 2.5% of premium
  x2      same, half-spread 5%
  ssvi    SSVI (rho=-0.7) on the smoothed-SKEW surface, half-spread 2.5% (about 1.3-1.7x more expensive)
  tick    base plus half-spread >= 0.05 index points and ask >= 0.10 index points
  rawskew linz model calibrated to the raw daily SKEW (noisy wing marks), half-spread 2.5%
Selection rule (fixed before running): the configuration with the highest DEV CAGR in the base case.
Outputs: grid_dev.csv, bench_dev.csv
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt  # noqa: E402

OUT = Path(__file__).parent
A, B = "1990-01-01", "2007-12-31"


def main():
    df = bt.load("_s21").loc[A:B]
    raw = bt.load("").loc[A:B]
    prs = {"linz": bt.Pricer(df, "linz"), "ssvi": bt.Pricer(df, "ssvi"), "raw": bt.Pricer(raw, "linz")}
    spy, _ = bt.bench(df, "spy")
    rows = []
    for name, kw in [("spy", {}), ("97_3_bills", {}), ("cashcrash_dd20", dict(dd_trig=0.20)),
                     ("cashcrash_dd30", dict(dd_trig=0.30))]:
        kind = name.split("_")[0] if name != "97_3_bills" else "97_3"
        nav, st = bt.bench(df, kind, **kw)
        rows.append(dict(name=name, **bt.metrics(nav.nav, spy.nav), **st))
    bench = pd.DataFrame(rows)
    bench.to_csv(OUT / "bench_dev.csv", index=False, float_format="%.5f")
    print(bench.round(4).to_string())
    cases = {"base": ("linz", dict(hpct=0.025)), "x2": ("linz", dict(hpct=0.05)),
             "ssvi": ("ssvi", dict(hpct=0.025)),
             "tick": ("linz", dict(hpct=0.025, floor=0.05, min_ask=0.10)),
             "rawskew": ("raw", dict(hpct=0.025))}
    out = []
    for depth, tenor, budget, monet in itertools.product([0.20, 0.30], [2, 4], [0.01, 0.02, 0.033], [None, 5]):
        rec = dict(depth=depth, tenor=tenor, budget=budget, monet=monet or 0)
        for cname, (pm, kw) in cases.items():
            d = raw if pm == "raw" else df
            res, st, _ = bt.run(d, prs[pm], depth, tenor, budget, monet, **kw)
            m = bt.metrics(res.nav, spy.nav)
            rec[f"{cname}_cagr"] = m["cagr"]
            rec[f"{cname}_exc"] = m["excess_vs_ref"]
            rec[f"{cname}_maxdd"] = m["maxdd"]
            if cname == "base":
                rec["base_vol"] = m["vol"]
                rec["base_net_bleed_py"] = (st["prem_paid"] - st["sale_proc"]) / 18.0
                rec["base_n_monet"] = st["n_monetize"]
                rec["base_avg_put_w"] = res.put_w.mean()
        out.append(rec)
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()
               if k in ("depth", "tenor", "budget", "monet") or k.endswith("_exc")}, flush=True)
    g = pd.DataFrame(out)
    g.to_csv(OUT / "grid_dev.csv", index=False, float_format="%.5f")
    best = g.sort_values("base_cagr", ascending=False).iloc[0]
    print("\nselected (max base DEV CAGR):\n", best.round(4).to_string())
    print("\nconfigs beating SPY in base:", int((g.base_exc > 0).sum()), "of", len(g),
          "| in all of base/x2/ssvi/tick:", int(((g[["base_exc", "x2_exc", "ssvi_exc", "tick_exc"]] > 0).all(1)).sum()))


if __name__ == "__main__":
    main()
