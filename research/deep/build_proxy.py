"""Long-history proxy universe (1962-1999) for independent validation. No overlap with ETF data.

Columns (simple daily total returns):
  SPY        US total market (French Mkt) - stands in for SPY
  i49_*      49 value-weighted US industries (French)
  T10, T5    synthetic constant-maturity Treasuries: a par bond bought at yesterday's yield,
             repriced at today's yield (exact annuity pricing, semiannual coupons) + 1 day of carry
  XAU        Philadelphia gold & silver index (price only, from 1984) - gold-equity proxy
Writes data/proxy_long.csv (not tradeable; validation only).
"""
import pathlib

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from harness.data import load


def par_bond_returns(yield_pct: pd.Series, maturity: float) -> pd.Series:
    y0 = yield_pct.shift(1) / 100.0
    y1 = yield_pct / 100.0
    n = 2 * maturity
    c = y0 / 2                      # semiannual coupon of a bond issued at par yesterday
    r = y1 / 2
    disc = (1 + r) ** (-n)
    price = c / r * (1 - disc) + disc
    return (price - 1.0) + y0 / 252.0


def main() -> None:
    base = load(until="1999-12-31")
    cal = base.dates[base.dates >= "1962-01-01"]
    out = pd.DataFrame(index=cal)
    out["SPY"] = base.returns["Mkt"].reindex(cal)
    out = out.join(base.extra.reindex(cal))
    for tk, col, mat in (("^TNX", "T10", 10.0), ("^FVX", "T5", 5.0)):
        y = yf.download(tk, period="max", auto_adjust=False, progress=False)["Close"].squeeze()
        y.index = pd.to_datetime(y.index).tz_localize(None)
        y = y.reindex(cal).ffill()
        out[col] = par_bond_returns(y, mat)
    xau = yf.download("^XAU", period="max", auto_adjust=False, progress=False)["Close"].squeeze()
    xau.index = pd.to_datetime(xau.index).tz_localize(None)
    out["XAU"] = xau.reindex(cal).pct_change(fill_method=None)
    out = out.iloc[1:]
    out.index.name = "date"
    out.to_csv(ROOT / "data" / "proxy_long.csv", float_format="%.8f")
    ann = (1 + out.fillna(0)).prod() ** (252 / len(out)) - 1
    print(out.shape, out.index[0].date(), out.index[-1].date())
    print(ann[["SPY", "T10", "T5", "XAU"]].round(4).to_string())


if __name__ == "__main__":
    main()
