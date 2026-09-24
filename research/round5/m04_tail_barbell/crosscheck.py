"""Real Cboe benchmark indices vs S&P 500 TR, alongside the model barbell (run after the TEST run).

  VXTH  Cboe VIX Tail Hedge Index (since 2006-03-31): S&P 500 TR plus 1-month 30-delta VIX calls,
        0-1% of the portfolio depending on the VIX level. This is the only real published tail-hedge index on cdn.cboe.com.
  PPUT  Cboe S&P 500 5% Put Protection Index (full hedge with 1-month 5%-OTM puts).
  CLL   Cboe S&P 500 95-110 Collar (since 2008-08-26 on the CDN).
Real traded prices, no fees. Output: crosscheck.csv, crosscheck_yearly.csv
"""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt  # noqa: E402

OUT = Path(__file__).parent
D = bt.D


def stats(s):
    s = s.dropna()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    return dict(start=s.index[0].date(), cagr=(s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1,
                maxdd=(s / s.cummax() - 1).min(), vol=s.pct_change().std() * math.sqrt(252))


def main():
    p = pd.read_pickle(D / "panel.pkl")
    tr = (1 + p.r_tr.fillna(0)).cumprod()
    spy = (1 + p.r_eq.fillna(0)).cumprod()
    idx = {"SP500TR": tr, "SPY_TR": spy, "PPUT": p.PPUT, "VXTH": p.VXTH, "CLL": p.CLL}
    dt = pd.read_csv(OUT / "daily_test.csv.gz", index_col=0, parse_dates=True)
    dd = pd.read_csv(OUT / "daily_dev.csv.gz", index_col=0, parse_dates=True)
    rows = []
    windows = [("DEV 1990-2007", "1990-01-02", "2007-12-31"), ("TEST 2008-2026", "2008-01-02", "2026-09-22"),
               ("VXTH life 2006-04..2026", "2006-03-31", "2026-09-22"), ("CLL life 2008-09..2026", "2008-08-26", "2026-09-22")]
    for wname, a, b in windows:
        for k, s in idx.items():
            sub = s.loc[a:b].dropna()
            if len(sub) < 250 or sub.index[0] > pd.Timestamp(a) + pd.Timedelta(days=10):
                continue
            rows.append(dict(window=wname, series=k, **stats(sub)))
        src = dd if wname.startswith("DEV") else dt
        if wname.startswith(("DEV", "TEST")):
            for k in ["barbell_base", "canon_base"]:
                rows.append(dict(window=wname, series=k + " (model)", **stats(src[k])))
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "crosscheck.csv", index=False, float_format="%.4f")
    print(R.round(4).to_string())
    Y = pd.DataFrame({k: s.loc["2006-03-31":].resample("YE").last() for k, s in idx.items()})
    Y = Y.pct_change()
    Y.index = Y.index.year
    Y["VXTH-SP500TR"] = Y.VXTH - Y.SP500TR
    Y["PPUT-SP500TR"] = Y.PPUT - Y.SP500TR
    Y.to_csv(OUT / "crosscheck_yearly.csv", float_format="%.4f")
    print(Y.round(3).to_string())


if __name__ == "__main__":
    main()
