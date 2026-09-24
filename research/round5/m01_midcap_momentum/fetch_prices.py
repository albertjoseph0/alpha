"""Download daily adjusted close + volume from yfinance for every ticker that was ever an S&P 400
member since 2011-12 (reconstructed). Cached in chunks; polite sleeps."""
import time
import yfinance as yf
from common import *

M = pd.read_csv(DATA / "membership_monthly.csv")
tick = sorted(t for t in M.ticker.unique() if "#" not in t)
tick = sorted(set(tick) | {"SPY", "MDY", "IJH", "RSP"})
cdir = DATA / "yf_chunks"
cdir.mkdir(exist_ok=True)
CH = 40
for i in range(0, len(tick), CH):
    f = cdir / f"chunk_{i:04d}.pkl"
    if f.exists():
        continue
    sub = tick[i:i + CH]
    for attempt in range(3):
        try:
            d = yf.download(sub, start="2010-06-01", end="2026-09-24", auto_adjust=True,
                            progress=False, threads=False, group_by="column")
            break
        except Exception as e:
            print("retry", i, e)
            time.sleep(10)
    d[["Close", "Volume"]].to_pickle(f)
    print(i, len(sub), d["Close"].notna().any().sum(), flush=True)
    time.sleep(2)

C = pd.concat([pd.read_pickle(f)["Close"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
V = pd.concat([pd.read_pickle(f)["Volume"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
C = C.loc[:, ~C.columns.duplicated()]
V = V.loc[:, ~V.columns.duplicated()]
C.to_pickle(DATA / "close.pkl")
V.to_pickle(DATA / "volume.pkl")
print("tickers with any data:", C.notna().any().sum(), "of", len(tick))
