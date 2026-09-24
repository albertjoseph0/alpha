"""Download benchmark / comparison ETFs (adjusted close) into a NEW file bench_close.pkl
(close.pkl is shared with m11 and must not be overwritten).
  IJH, MDY : cap-weighted S&P 400 (mid-cap benchmark)
  EWMC     : S&P 400 equal weight (diagnostic for survivorship/membership bias of the rebuilt universe)
  XMMO     : Invesco S&P MidCap 400 Momentum ETF (tracks the S&P 400 momentum index since 2019-06)
  SPY      : main benchmark
"""
import time
import yfinance as yf
from common import *

TICK = ["SPY", "IJH", "MDY", "EWMC", "XMMO", "XMHQ", "RSP"]
f = DATA / "bench_close.pkl"
old = pd.read_pickle(f) if f.exists() else pd.DataFrame()
out = {c: old[c] for c in old.columns if old[c].notna().sum() > 100}
for t in TICK:
    if t in out:
        continue
    for attempt in range(4):
        try:
            d = yf.download(t, start="2010-06-01", end="2026-09-24", auto_adjust=True, progress=False, threads=False)
            if len(d):
                out[t] = d["Close"].squeeze()
                break
        except Exception as e:
            print("retry", t, e)
        time.sleep(20)
    print(t, len(out.get(t, [])), flush=True)
    time.sleep(3)
B = pd.DataFrame(out)
B.to_pickle(f)
print(B.notna().sum())
