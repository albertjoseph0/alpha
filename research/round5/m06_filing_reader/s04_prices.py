"""Daily adjusted OHLC from yfinance for every universe ticker + SPY (2019-09 .. now)."""
import time
import pandas as pd, yfinance as yf
from common import DATA

iv = pd.read_csv(DATA / "sp500_pit_intervals.csv")
tick = sorted(set(iv.ticker)) + ["SPY"]
out = {}
for i in range(0, len(tick), 50):
    chunk = [t.replace(".", "-") for t in tick[i:i + 50]]
    df = yf.download(chunk, start="2019-09-01", end="2026-09-24", auto_adjust=True, progress=False,
                     group_by="ticker", threads=False)
    for t in chunk:
        try:
            d = df[t][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "Close"])
        except KeyError:
            continue
        if len(d):
            out[t] = d
    print(i, len(out), flush=True)
    time.sleep(2)
px = pd.concat(out, names=["ticker", "date"]).reset_index()
px.to_parquet(DATA / "prices.parquet")
miss = [t for t in tick if t.replace(".", "-") not in out]
print("got", len(out), "missing", len(miss)); print(miss)
