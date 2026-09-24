"""Prices for the allocator: ETF OHLC (yfinance, adjusted), index proxies, FRED yields.

Writes data/round6/j03_fomc/prices.parquet with, per asset X:
  X_cc  close-to-close total return of the tradeable ETF, spliced with a proxy before ETF inception
  X_co  close(t-1)->open(t) return (overnight), NaN where no open is available (proxy era)
  X_px  1 if the value is a proxy (pre-inception)
plus CASH (3m T-bill accrual) and yields DGS2/DGS10.
Proxies (DEV only, pre-inception): QQQ <- ^NDX price + 0.5%/yr, IWM <- ^RUT price + 1.5%/yr,
TLT <- par bond on DGS20 (N=20), IEF <- par bond on avg(DGS7,DGS10) (N=8.5), SHY <- par bond on DGS2 (N=1.9).
GLD has no proxy: it is simply not in the menu before 2004-11-19.
"""
import io
import pathlib
import time
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "round6" / "j03_fomc"
UA = "alpha-research contact@alpha-research.dev"
ETFS = ["SPY", "QQQ", "IWM", "TLT", "IEF", "SHY", "GLD"]


def fred(series):
    p = D / "raw" / f"fred_{series}.csv"
    if not p.exists():
        req = urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", headers={"User-Agent": UA})
        for k in range(5):
            try:
                p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
                break
            except Exception as e:  # noqa  (FRED returns sporadic 403s)
                print("fred retry", series, e)
                time.sleep(5 * (k + 1))
        time.sleep(1)
    s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
    return pd.to_numeric(s, errors="coerce")


def par_bond_ret(y, N):
    """Daily total return of a constant-maturity par bond from a yield series in percent."""
    y = y.ffill() / 100.0
    y0 = y.shift(1)
    dt = pd.Series(y.index, index=y.index).diff().dt.days.fillna(1) / 365.0
    # price at yield y1 of a bond with coupon y0 and maturity N (semiannual), minus par + carry
    c = y0 / 2
    n = 2 * N
    r1 = y / 2
    price = c * (1 - (1 + r1) ** (-n)) / r1 + (1 + r1) ** (-n)
    return price - 1 + y0 * dt


def main():
    raw = D / "raw" / "yf_ohlc.pkl"
    if raw.exists():
        px = pd.read_pickle(raw)
    else:
        px = yf.download(ETFS + ["^GSPC", "^NDX", "^RUT"], start="1992-01-01", auto_adjust=True, progress=False,
                         threads=False)
        px.to_pickle(raw)
    C, O = px["Close"], px["Open"]
    cal = C["^GSPC"].dropna().index
    cal = cal[cal >= "1993-01-01"]
    C, O = C.reindex(cal), O.reindex(cal)
    out = pd.DataFrame(index=cal)
    y = {s: fred(s).reindex(cal).ffill() for s in ["DGS2", "DGS7", "DGS10", "DGS20", "DTB3"]}
    dt = pd.Series(cal, index=cal).diff().dt.days.fillna(1)
    out["CASH_cc"] = (y["DTB3"].shift(1) / 100) * dt / 360
    out["DGS2"], out["DGS10"] = y["DGS2"], y["DGS10"]
    proxy = {
        "QQQ": C["^NDX"].pct_change(fill_method=None) + 0.005 * dt / 365,
        "IWM": C["^RUT"].pct_change(fill_method=None) + 0.015 * dt / 365,
        "TLT": par_bond_ret(y["DGS20"], 20),
        "IEF": par_bond_ret((y["DGS7"] + y["DGS10"]) / 2, 8.5),
        "SHY": par_bond_ret(y["DGS2"], 1.9),
    }
    for e in ETFS:
        cc = C[e].pct_change(fill_method=None)
        co = O[e] / C[e].shift(1) - 1
        first = C[e].first_valid_index()
        isproxy = pd.Series(cal < first, index=cal).astype(int)
        if e in proxy:
            cc = cc.where(~isproxy.astype(bool), proxy[e])
        out[e + "_cc"] = cc
        out[e + "_co"] = co.where(~isproxy.astype(bool))
        out[e + "_px"] = isproxy
    out = out.iloc[1:]
    # tracking check of proxies vs ETFs where both exist (2003-2012)
    chk = {}
    for e in ["QQQ", "IWM", "TLT", "IEF", "SHY"]:
        a = C[e].pct_change(fill_method=None)["2003":"2012"]
        b = proxy[e]["2003":"2012"]
        ok = a.notna() & b.notna()
        chk[e] = dict(corr=np.corrcoef(a[ok], b[ok])[0, 1], etf_ann=(1 + a[ok]).prod() ** (252 / ok.sum()) - 1,
                      proxy_ann=(1 + b[ok]).prod() ** (252 / ok.sum()) - 1)
    chk = pd.DataFrame(chk).T
    print(chk.round(4))
    chk.to_csv(D / "proxy_check.csv")
    out.to_parquet(D / "prices.parquet")
    print(out.index.min(), out.index.max(), out.shape)
    print(out[[c for c in out.columns if c.endswith("_px")]].sum())


if __name__ == "__main__":
    main()
