"""Upper bound (uses hindsight on purpose; NOT a strategy): how much could the barbell add with
perfect monetisation timing?

Each monthly tranche (same buy rule as backtest.run: K = S(1-depth), expiry month m+tenor,
premium budget/12 * NAV at the ask) is sold at the day with the highest model bid over
  mode "month": its first month (up to the next roll; same holding window as the real rule), or
  mode "life":  its whole life up to 5 days before expiry (tranches overlap).
Sale proceeds go into the equity sleeve on the sale date. Base pricing (linz, s21 surface), half-spread 2.5%.
Output: oracle_bound.csv
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt  # noqa: E402

OUT = Path(__file__).parent
PER = {"dev": ("1990-01-01", "2007-12-31"), "test": ("2008-01-01", "2026-12-31")}


def oracle(df, pr, depth, tenor, budget, mode, hpct=0.025):
    idx, S, r_eq = df.index, df.SPX.values, df.r_eq.values
    n = len(idx)
    rolls = [0] + [i for i in range(1, n) if idx[i].month != idx[i - 1].month]
    eq = 1.0
    open_ = []  # dicts: K, exp, n, sell_i
    nav = np.empty(n)
    for i in range(n):
        if i > 0:
            eq *= 1 + r_eq[i]
        # sales scheduled today
        keep = []
        for t in open_:
            if t["sell_i"] == i:
                mid = pr.put(i, t["K"], (t["exp"] - idx[i]).days / 365)
                eq += t["n"] * mid * (1 - hpct)
            else:
                keep.append(t)
        open_ = keep
        marks = sum(t["n"] * pr.put(i, t["K"], (t["exp"] - idx[i]).days / 365) for t in open_)
        navi = eq + marks
        if i in rolls:
            K = 5.0 * round(S[i] * (1 - depth) / 5.0)
            exp = bt.expiry_for(idx[i], tenor)
            mid = pr.put(i, K, (exp - idx[i]).days / 365)
            spend = budget / 12 * navi
            nc = spend / (mid * (1 + hpct))
            eq -= spend
            nxt = [r for r in rolls if r > i]
            if mode == "month":
                end = nxt[0] if nxt else n - 1
            else:
                end = int(np.searchsorted(idx.values, (exp - pd.Timedelta(days=5)).to_datetime64()))
                end = min(end, n - 1)
            js = range(i + 1, end + 1)
            if len(js) == 0:
                js = [i]
            bids = [pr.put(j, K, max((exp - idx[j]).days, 0) / 365) for j in js]
            sell_i = list(js)[int(np.argmax(bids))]
            open_.append(dict(K=K, exp=exp, n=nc, sell_i=sell_i))
            navi = eq + sum(t["n"] * pr.put(i, t["K"], (t["exp"] - idx[i]).days / 365) for t in open_)
        nav[i] = navi
    return pd.Series(nav, index=idx)


def main():
    rows = []
    for p, (a, b) in PER.items():
        df = bt.load("_s21").loc[a:b]
        pr = bt.Pricer(df, "linz")
        spy, _ = bt.bench(df, "spy")
        for depth, tenor, budget, mode in itertools.product([0.2, 0.3], [2, 4], [0.033], ["month", "life"]):
            nav = oracle(df, pr, depth, tenor, budget, mode)
            m = bt.metrics(nav, spy.nav)
            rec = dict(period=p, depth=depth, tenor=tenor, budget=budget, mode=mode, cagr=m["cagr"],
                       excess=m["excess_vs_ref"], maxdd=m["maxdd"])
            if p == "test":
                rec["excl_2008_2020_excess"] = bt.cagr_excl(nav, [2008, 2020]) - bt.cagr_excl(spy.nav, [2008, 2020])
            rows.append(rec)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}, flush=True)
    pd.DataFrame(rows).to_csv(OUT / "oracle_bound.csv", index=False, float_format="%.5f")


if __name__ == "__main__":
    main()
