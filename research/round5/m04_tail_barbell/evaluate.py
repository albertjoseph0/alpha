"""Full evaluation of the frozen configuration (frozen_config.json) over one period.

usage: python evaluate.py dev|test
  dev  = 1990-01-02 .. 2007-12-31,  test = 2008-01-02 .. last date (2026-09-22). NAV starts at 1 on the
  first day of the period (the test period is run fresh, it does not inherit dev positions).
Writes eval_<p>.csv (all cases + benchmarks), yearly_<p>.csv, excl_<p>.csv (CAGR without 2008 / 2020),
       trades_<p>.csv (base case), daily_<p>.csv.gz, grid_<p>.csv (all 24 configs, descriptive only).
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt  # noqa: E402

OUT = Path(__file__).parent
PER = {"dev": ("1990-01-01", "2007-12-31"), "test": ("2008-01-01", "2026-12-31")}


def main(p):
    a, b = PER[p]
    cfg = json.load(open(OUT / "frozen_config.json"))
    df = bt.load("_s21").loc[a:b]
    raw = bt.load("").loc[a:b]
    prs = {"linz": bt.Pricer(df, "linz"), "ssvi": bt.Pricer(df, "ssvi"), "raw": bt.Pricer(raw, "linz")}
    cases = {"base": ("linz", dict(hpct=0.025)), "x2": ("linz", dict(hpct=0.05)),
             "ssvi": ("ssvi", dict(hpct=0.025)),
             "ssvi_x2": ("ssvi", dict(hpct=0.05)),
             "tick": ("linz", dict(hpct=0.025, floor=0.05, min_ask=0.10)),
             "rawskew": ("raw", dict(hpct=0.025))}
    navs, rows = {}, []
    spy, _ = bt.bench(df, "spy")
    for name, kind, kw in [("SPY", "spy", {}), ("97SPY_3bills", "97_3", {}),
                           ("cashcrash_dd20", "cashcrash", dict(dd_trig=0.20)),
                           ("cashcrash_dd30", "cashcrash", dict(dd_trig=0.30))]:
        nav, st = bt.bench(df, kind, **kw)
        navs[name] = nav.nav
        rows.append(dict(name=name, **bt.metrics(nav.nav, spy.nav), **st))
    for cname, (pm, kw) in cases.items():
        d = raw if pm == "raw" else df
        res, st, tr = bt.run(d, prs[pm], cfg["depth"], cfg["tenor"], cfg["budget"], cfg["monet"] or None, **kw)
        navs["barbell_" + cname] = res.nav
        yrs = (res.index[-1] - res.index[0]).days / 365.25
        rows.append(dict(name="barbell_" + cname, **bt.metrics(res.nav, spy.nav), **st,
                         net_bleed_py=(st["prem_paid"] - st["sale_proc"]) / yrs, avg_put_w=res.put_w.mean()))
        if cname == "base":
            t = pd.DataFrame(tr, columns=["date", "kind", "proceeds", "cost"])
            t["multiple"] = t.proceeds / t.cost
            t.to_csv(OUT / f"trades_{p}.csv", index=False, float_format="%.6f")
            put_w = res.put_w
    # descriptive (declared in PREREG): canonical Universa-like config 30% OTM, 2m, 3.3%/yr, 5x monetize
    for cname in ["base", "x2", "ssvi"]:
        pm, kw = cases[cname]
        res, st, tr = bt.run(df, prs[pm], 0.30, 2, 0.033, 5, **kw)
        navs["canon_" + cname] = res.nav
        yrs = (res.index[-1] - res.index[0]).days / 365.25
        rows.append(dict(name="canon_" + cname, **bt.metrics(res.nav, spy.nav), **st,
                         net_bleed_py=(st["prem_paid"] - st["sale_proc"]) / yrs, avg_put_w=res.put_w.mean()))
        if cname == "base":
            t = pd.DataFrame(tr, columns=["date", "kind", "proceeds", "cost"])
            t["multiple"] = t.proceeds / t.cost
            t.to_csv(OUT / f"trades_canon_{p}.csv", index=False, float_format="%.6f")
    ev = pd.DataFrame(rows)
    ev.to_csv(OUT / f"eval_{p}.csv", index=False, float_format="%.5f")
    print(ev.round(4).to_string())
    N = pd.DataFrame(navs)
    N["put_w_base"] = put_w
    N.to_csv(OUT / f"daily_{p}.csv.gz", float_format="%.7f")
    Y = pd.DataFrame({k: bt.yearly(v) for k, v in navs.items()})
    Y.index = Y.index.year
    Y["base_minus_SPY"] = Y["barbell_base"] - Y["SPY"]
    Y.to_csv(OUT / f"yearly_{p}.csv", float_format="%.4f")
    print(Y.round(3).to_string())
    ex = []
    for k, v in navs.items():
        rec = dict(name=k, cagr=bt.metrics(v)["cagr"])
        for yrs_ in ([2008], [2020], [2008, 2020], [2000, 2001, 2002], [1998]):
            if any((v.index.year == y).any() for y in yrs_):
                rec["excl_" + "_".join(map(str, yrs_))] = bt.cagr_excl(v, yrs_)
        ex.append(rec)
    E = pd.DataFrame(ex)
    E.to_csv(OUT / f"excl_{p}.csv", index=False, float_format="%.5f")
    print(E.round(4).to_string())
    # descriptive: all 24 configs, base and ssvi cases (no reselection)
    g = []
    for depth, tenor, budget, monet in itertools.product([0.20, 0.30], [2, 4], [0.01, 0.02, 0.033], [None, 5]):
        rec = dict(depth=depth, tenor=tenor, budget=budget, monet=monet or 0)
        for cname in ["base", "x2", "ssvi"]:
            pm, kw = cases[cname]
            res, _, _ = bt.run(df, prs[pm], depth, tenor, budget, monet, **kw)
            rec[cname + "_exc"] = bt.metrics(res.nav, spy.nav)["excess_vs_ref"]
        g.append(rec)
    G = pd.DataFrame(g)
    G.to_csv(OUT / f"grid_{p}.csv", index=False, float_format="%.5f")
    print(G.round(4).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
