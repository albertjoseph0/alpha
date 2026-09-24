"""Universe: point-in-time S&P 500 + S&P 400 monthly membership with a ticker -> CIK map.
CIK sources (in order): m06 S&P 500 intervals (cik), m06 ticker_cik.csv, SEC company_tickers.json (current).
-> DATA/universe_monthly.parquet [month_end, ticker, idx, cik], DATA/ticker_cik.csv"""
import json
import pandas as pd
from common import DATA, M06, membership, close

m = membership()
cmap = {}
sec = json.load(open(M06 / "company_tickers.json"))
for v in sec.values():
    cmap.setdefault(v["ticker"].upper(), int(v["cik_str"]))
tc = pd.read_csv(M06 / "ticker_cik.csv").dropna(subset=["cik"])
for r in tc.itertuples():
    cmap[r.ticker] = int(r.cik)          # m06's map is point-in-time for S&P 500 names -> overrides current map
iv = pd.read_csv(M06 / "sp500_pit_intervals.csv").dropna(subset=["cik"])
for r in iv.itertuples():
    cmap[r.ticker] = int(r.cik)


def cik_of(t):
    for k in (t, t.replace(".", "-"), t.replace("-", "."), t.replace("-", "")):
        if k in cmap:
            return cmap[k]
    return None


m["cik"] = m.ticker.map(cik_of)
m.to_parquet(DATA / "universe_monthly.parquet")
px = set(close().columns)
tick = m.groupby("ticker").agg(cik=("cik", "first"), idx=("idx", "first"), first=("month_end", "min"),
                               last=("month_end", "max")).reset_index()
tick["has_px"] = tick.ticker.isin(px)
tick.to_csv(DATA / "ticker_cik.csv", index=False)
print("tickers", len(tick), "with cik", tick.cik.notna().sum(), "with px", tick.has_px.sum(),
      "cik&px", (tick.cik.notna() & tick.has_px).sum())
g = m.assign(ok=m.cik.notna() & m.ticker.isin(px)).groupby(m.month_end.dt.year).ok.mean()
print("member-month share with cik & price, by year:\n", g.round(3).to_string())
print("distinct CIKs", m.cik.nunique())
