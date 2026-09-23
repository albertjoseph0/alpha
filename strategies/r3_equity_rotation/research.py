"""Evaluate named configurations of EquityRotation on etf_dev / etf_dev_a / etf_dev_b and
append each to research/evals.log (one configuration = one line, all three CAGRs).

usage: .venv/bin/python strategies/r3_equity_rotation/research.py <config-name> [...]
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys, json, datetime, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness
from strategy import EquityRotation, equity_universe

LOG = pathlib.Path(__file__).resolve().parents[2] / "research" / "evals.log"
US_ONLY = [t for t in equity_universe() if harness.etf_meta().loc[t, "asset_class"] != "intl_equity"]

CONFIGS = {
    # 1. a-priori core design
    "core": dict(trend_lb=None),   # trend check on the 12-1 window itself
    # NOTE: strategy.py defaults were later set to the chosen "trend6" design (trend_lb=126);
    # earlier configs pin trend_lb=None explicitly so this file reproduces the log.
    # 2-4. after core failed dev_b (2008 held EWZ/XME/FXI; 2009 stuck in IEF; 2011 in commodity
    #      equities): faster absolute-trend window, and vol-adjusted ranking for a mixed-vol sleeve
    "trend6": dict(trend_lb=126),
    "sharpe": dict(score="sharpe", trend_lb=None),
    "sharpe_trend6": dict(score="sharpe", trend_lb=126),
    # ablations / sensitivity around the trend6 design (one change at a time)
    "t6_no_trend": dict(trend=False, trend_lb=None),
    "t6_trend3": dict(trend_lb=63),
    "t6_trend9": dict(trend_lb=189),
    "t6_no_dedup": dict(trend_lb=126, max_corr=1.0),
    "t6_eqwt": dict(trend_lb=126, rank_weight=False),
    "t6_single_tranche": dict(trend_lb=126, tranche_days=(0,)),
    "t6_us_only": dict(trend_lb=126, universe=US_ONLY),
    "t6_frac_1_3": dict(trend_lb=126, frac=1 / 3),
    "t6_corr_80": dict(trend_lb=126, max_corr=0.80),
    "t6_trend_cash": dict(trend_lb=126, fallback="NONE"),
    # single tranche beat stag4 by ~2-3 pts: day-0 luck or responsiveness? check another offset,
    # and a full-book refresh on each of days 0/5/10/15 (responsive, no single-day timing luck)
    "t6_single_day10": dict(trend_lb=126, tranche_days=(10,)),
    "t6_refresh4": dict(trend_lb=126, blend=False),
}


def evaluate(key):
    data = harness.load_etf_dev()
    out = {}
    for w in ("etf_dev", "etf_dev_a", "etf_dev_b"):
        s = EquityRotation(name=f"r3:eqrot_{key}", **CONFIGS[key])
        out[w] = harness.run(s, window=w, data=data, ledger=False).cagr
    line = (f"{datetime.date.today()} r3_equity_rotation r3:eqrot_{key} {json.dumps({k: (str(v) if isinstance(v, tuple) else v) for k, v in CONFIGS[key].items() if k != 'universe'} | ({'universe': 'US_ONLY'} if 'universe' in CONFIGS[key] else {}))} "
            f"etf_dev={out['etf_dev']:.2%} etf_dev_a={out['etf_dev_a']:.2%} etf_dev_b={out['etf_dev_b']:.2%}")
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


if __name__ == "__main__":
    for k in sys.argv[1:]:
        evaluate(k)
