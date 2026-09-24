"""Daily adjusted Open/Close (yfinance, auto_adjust) for every universe ticker that has m11 price data, plus SPY.
Chunked cache DATA/yf/chunk_*.pkl -> DATA/open.parquet, DATA/close.parquet (float32, dates x tickers).
Tickers yfinance no longer serves fall back to m11's close (read-only), with open = NaN (such events use
the next close as a conservative entry, flagged)."""
import time
import yfinance as yf
from common import *

U = pd.read_parquet(DATA / "universe.parquet")
tick = sorted(set(U[U.has_px].ticker)) + ["SPY"]
cdir = DATA / "yf"
cdir.mkdir(exist_ok=True)
CH = 40
for i in range(0, len(tick), CH):
    f = cdir / f"chunk_{i:04d}.pkl"
    if f.exists():
        continue
    sub = tick[i:i + CH]
    d = None
    for attempt in range(4):
        try:
            d = yf.download(sub, start="2012-06-01", end="2026-09-24", auto_adjust=True, progress=False,
                            threads=False, group_by="column")
            break
        except Exception as e:  # noqa: BLE001
            print("retry", i, e, flush=True)
            time.sleep(15)
    d[["Open", "Close"]].astype("float32").to_pickle(f)
    print(i, len(sub), int(d["Close"].notna().any().sum()), flush=True)
    time.sleep(2)

O = pd.concat([pd.read_pickle(f)["Open"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
C = pd.concat([pd.read_pickle(f)["Close"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
O = O.loc[:, ~O.columns.duplicated()]; C = C.loc[:, ~C.columns.duplicated()]
C11 = pd.read_pickle(M11 / "close.pkl")
miss = [t for t in tick if t not in C.columns or C[t].notna().sum() == 0]
print("missing from fresh download:", len(miss), miss[:30])
C11 = C11.reindex(C.index)
for t in miss:
    if t in C11.columns:
        C[t] = C11[t]
        O[t] = np.nan
O.index = pd.to_datetime(O.index); C.index = pd.to_datetime(C.index)
O.astype("float32").to_parquet(DATA / "open.parquet")
C.astype("float32").to_parquet(DATA / "close.parquet")
print(O.shape, C.shape, C.index.min(), C.index.max())
