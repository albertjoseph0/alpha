"""POST-TEST robustness grid (TAINTED: written after the one pre-registered TEST run).

On TEST, the pre-registered rule sold every tranche after one month and monetised at 5x. In 2020 that
cashed out at about 6x, while the same puts held to mid-March would have been worth 35-60x in the model.
This grid asks whether a wider rule family, with overlapping tranches held to about expiry and a higher
monetisation multiple, would have been chosen on DEV and would change the conclusion.
Selection is on DEV only (max base CAGR). TEST figures for the whole grid are printed as descriptive
and flagged tainted.
  depth {0.20, 0.30} x tenor {2, 4} x hold {1, tenor} x monet {None, 5, 20} x budget {0.01, 0.033}
Cases: base (linz, 2.5%), x2 (5%), ssvi (2.5%).  Output: grid2_ladder.csv
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt  # noqa: E402

OUT = Path(__file__).parent
PER = {"dev": ("1990-01-01", "2007-12-31"), "test": ("2008-01-01", "2026-12-31")}


def main():
    rows = []
    data = {}
    for p, (a, b) in PER.items():
        df = bt.load("_s21").loc[a:b]
        data[p] = (df, {"linz": bt.Pricer(df, "linz"), "ssvi": bt.Pricer(df, "ssvi")}, bt.bench(df, "spy")[0])
    cases = {"base": ("linz", 0.025), "x2": ("linz", 0.05), "ssvi": ("ssvi", 0.025)}
    for depth, tenor, hold_long, monet, budget in itertools.product([0.2, 0.3], [2, 4], [False, True], [None, 5, 20],
                                                                    [0.01, 0.033]):
        hold = tenor if hold_long else 1
        rec = dict(depth=depth, tenor=tenor, hold=hold, monet=monet or 0, budget=budget)
        for p in PER:
            df, prs, spy = data[p]
            for cname, (pm, h) in cases.items():
                res, st, _ = bt.run_ladder(df, prs[pm], depth, tenor, budget, monet, h, hold)
                m = bt.metrics(res.nav, spy.nav)
                rec[f"{p}_{cname}_exc"] = m["excess_vs_ref"]
                if cname == "base":
                    rec[f"{p}_base_cagr"] = m["cagr"]
                    rec[f"{p}_base_maxdd"] = m["maxdd"]
                    if p == "test":
                        rec["test_base_exc_excl_08_20"] = bt.cagr_excl(res.nav, [2008, 2020]) - bt.cagr_excl(spy.nav, [2008, 2020])
        rows.append(rec)
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if "cagr" not in k}, flush=True)
    g = pd.DataFrame(rows)
    g.to_csv(OUT / "grid2_ladder.csv", index=False, float_format="%.5f")
    best = g.sort_values("dev_base_cagr", ascending=False).iloc[0]
    print("\nDEV-selected (max dev base CAGR):\n", best.round(4).to_string())
    print("configs beating SPY on DEV base:", int((g.dev_base_exc > 0).sum()), "of", len(g))
    print("configs beating SPY on TEST base (tainted, descriptive):", int((g.test_base_exc > 0).sum()), "of", len(g))


if __name__ == "__main__":
    main()
