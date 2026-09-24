"""Pre-history closes (2018-08..2019-10) for the 12-1 momentum / vol features of 2020 events (prices.parquet starts
2019-09, which silently dropped all events before 2020-09). Spliced to prices.parquet by the median close ratio
on overlapping dates. Output: DATA/prices_pre.parquet (date, ticker, Open, Close; dates < 2019-09-03 only)."""
import time
import numpy as np, pandas as pd, yfinance as yf
from common import DATA

px = pd.read_parquet(DATA / "prices.parquet", columns=["date", "ticker", "Close"])
ref = px[px.date <= "2019-10-31"].pivot(index="date", columns="ticker", values="Close")
tick = sorted(px.ticker.unique())
out = []
for i in range(0, len(tick), 50):
    chunk = tick[i:i + 50]
    df = yf.download(chunk, start="2018-08-01", end="2019-11-01", auto_adjust=True, progress=False,
                     group_by="ticker", threads=False)
    for t in chunk:
        try:
            d = df[t][["Open", "Close"]].dropna()
        except KeyError:
            continue
        if not len(d) or t not in ref:
            continue
        ov = d.Close.reindex(ref.index).div(ref[t]).dropna()
        if len(ov) < 5:
            continue
        k = ov.median()
        d = d[d.index < pd.Timestamp("2019-09-03")] / k
        d["ticker"] = t
        out.append(d.rename_axis("date").reset_index())
    print(i, len(out), flush=True)
    time.sleep(2)
P = pd.concat(out, ignore_index=True)
P.to_parquet(DATA / "prices_pre.parquet")
print("tickers", P.ticker.nunique(), "rows", len(P), P.date.min(), P.date.max())
