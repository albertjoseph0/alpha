"""Retry yfinance one ticker at a time for tickers missing from prices.parquet (delisted names).
Writes prices_extra.parquet (prices.parquet is read by another agent: never overwritten)."""
import time
import pandas as pd, yfinance as yf
from common import DATA

px = pd.read_parquet(DATA / "prices.parquet", columns=["ticker"])
have = set(px.ticker)
iv = pd.read_csv(DATA / "sp500_pit_intervals.csv")
miss = sorted({t.replace(".", "-") for t in iv.ticker} - have)
out = {}
for t in miss:
    try:
        d = yf.download(t, start="2019-09-01", end="2026-09-24", auto_adjust=True, progress=False, threads=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "Close"])
        if len(d):
            out[t] = d
    except Exception as e:
        print(t, "err", e)
    time.sleep(1.0)
print("recovered", sorted(out), "still missing", sorted(set(miss) - set(out)))
if out:
    pd.concat(out, names=["ticker", "date"]).reset_index().to_parquet(DATA / "prices_extra.parquet")
