"""Build one aligned daily panel for the tail-barbell study.

Inputs (all in data/round5/m04_tail_barbell/, downloaded 2026-09-24):
  CBOE CDN: VIX, VIX3M, VIX6M, VIX1Y, SKEW, SPX, PPUT, VXTH, CLL
  yfinance: ^SP500TR, SPY (adj close), ^IRX, ^VIX3M (2006-07 onward; CBOE CDN only from 2009)
Output: data/round5/m04_tail_barbell/panel.parquet (pickle fallback)
"""
import numpy as np
import pandas as pd
from pathlib import Path

D = Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell"


def cboe(name, col=None):
    df = pd.read_csv(D / f"{name}_History.csv")
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    c = col or ("CLOSE" if "CLOSE" in df.columns else name)
    return df.set_index("DATE")[c].rename(name).astype(float)


def yf(name, col="Adj Close"):
    df = pd.read_csv(D / f"{name}_yf.csv", header=[0, 1], index_col=0)
    s = df[col].iloc[:, 0]
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[s.index.notna()].astype(float)
    return s.rename(name)


def main():
    spx = cboe("SPX")
    vix = cboe("VIX")
    skew = cboe("SKEW")
    vix3m = pd.concat([yf("VIX3M", "Close"), cboe("VIX3M")], axis=1)
    vix3m = vix3m.iloc[:, 1].fillna(vix3m.iloc[:, 0]).rename("VIX3M")  # CBOE first, yf to fill 2006-09
    vix6m = cboe("VIX6M")
    vix1y = cboe("VIX1Y")
    tr = yf("SP500TR")
    spy = yf("SPY")
    irx = yf("IRX", "Close")
    pput = cboe("PPUT")
    vxth = cboe("VXTH")
    cll = cboe("CLL")
    df = pd.concat([spx, tr, spy, vix, vix3m, vix6m, vix1y, skew, irx, pput, vxth, cll], axis=1)
    df = df[df.index >= "1989-01-01"]
    df = df[df["SPX"].notna() & df["VIX"].notna()]
    # SKEW has a few gaps; carry forward (published daily, info known at close)
    df["SKEW"] = df["SKEW"].ffill()
    df["IRX"] = df["IRX"].ffill()
    df["SP500TR"] = df["SP500TR"].ffill()
    # continuous risk-free from 13w T-bill discount yield
    d = df["IRX"] / 100.0
    df["r"] = -np.log(1 - d * 91 / 360) / (91 / 365)
    # trailing 1y dividend yield from TR vs price index (known at t)
    lr_tr = np.log(df["SP500TR"]).diff(252)
    lr_px = np.log(df["SPX"]).diff(252)
    q = ((lr_tr - lr_px) * 252 / 252).clip(0.0, 0.06)  # 252 trading days ~ 1y
    df["q"] = q.ffill().bfill()
    # equity sleeve daily total return: SPY adj close where available, else SP500TR minus 9.45bp/yr fee
    r_spy = df["SPY"].pct_change()
    r_tr = df["SP500TR"].pct_change() - 0.000945 / 252
    df["r_eq"] = r_spy.where(df["SPY"].shift(1).notna() & df["SPY"].notna(), r_tr)
    df["r_tr"] = df["SP500TR"].pct_change()
    # T-bill daily return (accrues on calendar days using prior-day rate)
    days = pd.Series(df.index, index=df.index).diff().dt.days.fillna(1)
    df["r_bill"] = np.exp(df["r"].shift(1).fillna(df["r"]) * days / 365) - 1
    df = df[df.index >= "1990-01-02"]
    df.to_pickle(D / "panel.pkl")
    print(df.describe().T[["count", "mean", "min", "max"]])
    print(df.index.min(), df.index.max())
    print(df[["VIX3M", "VIX6M", "VIX1Y"]].apply(lambda s: s.first_valid_index()))


if __name__ == "__main__":
    main()
