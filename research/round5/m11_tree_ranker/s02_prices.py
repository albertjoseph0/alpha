"""Daily adjusted close + volume (yfinance, 2010-06-01..2026-09-24) for S&P 500 PIT tickers not in
m01's close.pkl, plus sector ETFs and SPY. Chunked cache in DATA/yf_chunks. Then merge with m01's
S&P 400 panel (read-only) into DATA/close.pkl, DATA/volume.pkl (union universe)."""
import time
import yfinance as yf
from common import *

C1 = pd.read_pickle(M01 / "close.pkl")
V1 = pd.read_pickle(M01 / "volume.pkl")
have = set(C1.columns[C1.notna().any()])
a = pd.read_csv(DATA / "sp500_membership_monthly.csv")
need = sorted({t for t in a.ticker if "#" not in t} - have)
need = sorted(set(need) | set(SECTOR_ETFS) | {"SPY"})
print("to fetch:", len(need), flush=True)
cdir = DATA / "yf_chunks"
cdir.mkdir(exist_ok=True)
CH = 40
for i in range(0, len(need), CH):
    f = cdir / f"chunk_{i:04d}.pkl"
    if f.exists():
        continue
    sub = need[i:i + CH]
    d = None
    for attempt in range(3):
        try:
            d = yf.download(sub, start="2010-06-01", end="2026-09-24", auto_adjust=True,
                            progress=False, threads=False, group_by="column")
            break
        except Exception as e:
            print("retry", i, e, flush=True)
            time.sleep(10)
    d[["Close", "Volume"]].to_pickle(f)
    print(i, len(sub), d["Close"].notna().any().sum(), flush=True)
    time.sleep(2)

C2 = pd.concat([pd.read_pickle(f)["Close"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
V2 = pd.concat([pd.read_pickle(f)["Volume"] for f in sorted(cdir.glob("*.pkl"))], axis=1)
C2 = C2.loc[:, C2.notna().any()]
V2 = V2[C2.columns]
C1 = C1.loc[:, C1.notna().any()]
V1 = V1[C1.columns]
C2 = C2.drop(columns=[c for c in C2.columns if c in C1.columns])
V2 = V2[C2.columns]
C = pd.concat([C1, C2], axis=1).sort_index()
V = pd.concat([V1, V2], axis=1).sort_index()
C.index = pd.to_datetime(C.index); V.index = pd.to_datetime(V.index)
C = C.astype("float32"); V = V.astype("float32")
C.to_pickle(DATA / "close.pkl")
V.to_pickle(DATA / "volume.pkl")
print("merged panel:", C.shape, C.index.min(), C.index.max())
