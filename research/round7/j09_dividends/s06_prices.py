"""Daily Open / Close / Adj Close (yfinance, auto_adjust=False) for every universe ticker that has prices in m11's
panel, plus SPY and RSP. Adjusted open = Open * AdjClose / Close. Chunks of 40 tickers, resumable.
-> DATA/px_open_adj.pkl, DATA/px_close_adj.pkl, DATA/px_close_raw.pkl (float32, dates x tickers)"""
import time
import pandas as pd
import yfinance as yf
from common import DATA, close

tick = sorted(set(close().columns) | {"SPY", "RSP"})
cdir = DATA / "yf_chunks"
cdir.mkdir(exist_ok=True)
for i in range(0, len(tick), 40):
    f = cdir / f"c{i:04d}.pkl"
    if f.exists():
        continue
    sub = tick[i:i + 40]
    for att in range(4):
        try:
            d = yf.download(sub, start="2011-06-01", end="2026-09-24", auto_adjust=False, progress=False,
                            threads=False, group_by="column")
            break
        except Exception as e:  # noqa: BLE001
            print("retry", i, e, flush=True)
            time.sleep(20 * (att + 1))
    d = d[["Open", "Close", "Adj Close"]].astype("float32")
    d.to_pickle(f)
    print(i, d.shape, flush=True)
    time.sleep(2)
parts = [pd.read_pickle(f) for f in sorted(cdir.glob("c*.pkl"))]
allp = pd.concat(parts, axis=1)
o, c, a = allp["Open"], allp["Close"], allp["Adj Close"]
oa = (o * a / c).astype("float32")
oa.to_pickle(DATA / "px_open_adj.pkl")
a.to_pickle(DATA / "px_close_adj.pkl")
c.to_pickle(DATA / "px_close_raw.pkl")
print("tickers", a.shape[1], "with data", int(a.notna().any().sum()), a.index.min(), a.index.max())
