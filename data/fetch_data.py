"""Build data/market_daily.csv from the Kenneth R. French Data Library.

Output columns (all simple daily total returns, as decimals):
    Mkt                   US total market (CRSP value-weighted) = (Mkt-RF) + RF
    NoDur ... Other       12 value-weighted industry portfolios
    RF                    daily risk-free (1-month T-bill) rate

RF is derived from the *monthly* T-bill series (spread evenly across the trading
days of each month). The daily RF column in French's daily file is rounded to
0.01%/day, which can misstate cash returns by more than 1%/yr; the monthly
series is rounded to 0.01%/month (~0.06%/yr).

Usage:  python data/fetch_data.py
"""
from __future__ import annotations

import io
import pathlib
import urllib.request
import zipfile

import numpy as np
import pandas as pd

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "market_daily.csv"


def _download(name: str) -> str:
    RAW.mkdir(exist_ok=True)
    req = urllib.request.Request(BASE + name + ".zip", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    (RAW / f"{name}.zip").write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        member = z.namelist()[0]
        return z.read(member).decode("latin-1")


def _first_table(text: str, date_len: int) -> pd.DataFrame:
    """Parse the first comma-separated table whose rows start with a date of `date_len` digits."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(","))
    header = ["date"] + [c.strip() for c in lines[start].split(",")[1:]]
    rows = []
    for l in lines[start + 1:]:
        head = l.split(",")[0].strip()
        if not (head.isdigit() and len(head) == date_len):
            break  # end of first table
        rows.append([c.strip() for c in l.split(",")])
    df = pd.DataFrame(rows, columns=header)
    fmt = "%Y%m%d" if date_len == 8 else "%Y%m"
    df["date"] = pd.to_datetime(df["date"], format=fmt)
    df = df.set_index("date").astype(float)
    df = df.mask(df <= -99.99)  # French's missing-value codes (-99.99 / -999)
    return df / 100.0


def build() -> pd.DataFrame:
    ff_d = _first_table(_download("F-F_Research_Data_Factors_daily_CSV"), 8)
    ff_m = _first_table(_download("F-F_Research_Data_Factors_CSV"), 6)  # first table = monthly
    ind = _first_table(_download("12_Industry_Portfolios_daily_CSV"), 8)  # first table = value-weighted

    # Daily RF from monthly T-bill return, spread across that month's trading days.
    month = ff_d.index.to_period("M")
    n_days = pd.Series(1, index=ff_d.index).groupby(month).transform("size")
    rf_m = ff_m["RF"].copy()
    rf_m.index = rf_m.index.to_period("M")
    rf_month_for_day = pd.Series(month, index=ff_d.index).map(rf_m)
    # Months beyond the monthly file (if any): fall back to the daily file's rounded RF.
    rf_daily = (1.0 + rf_month_for_day) ** (1.0 / n_days) - 1.0
    rf_daily = rf_daily.fillna(ff_d["RF"])

    out = pd.DataFrame(index=ff_d.index)
    out["Mkt"] = ff_d["Mkt-RF"] + rf_daily
    out = out.join(ind, how="inner")
    out["RF"] = rf_daily.reindex(out.index)
    out.index.name = "date"
    if out.isna().any().any():
        bad = out.isna().sum()
        raise ValueError(f"missing values after build:\n{bad[bad > 0]}")
    return out


if __name__ == "__main__":
    df = build()
    df.to_csv(OUT, float_format="%.8f")
    print(f"wrote {OUT} rows={len(df)} {df.index[0].date()} -> {df.index[-1].date()}")
    ann = (1 + df).prod() ** (252 / len(df)) - 1
    print("full-sample annualized (approx):")
    print(ann.round(4).to_string())
