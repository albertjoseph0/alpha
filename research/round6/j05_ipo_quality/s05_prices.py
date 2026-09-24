"""Daily prices for IPO tickers from yfinance (cover-page ticker, then the CIK's current SEC ticker).
A series is accepted only if its first bar is within [-3, +20] calendar days of the 424B4 date.
Stores per-filing daily frames in prices/<acc>.parquet (adj close, unadjusted close, volume) and
price_map.csv (acc, ticker_used, status). Re-runnable: skips accs already in price_map.csv."""
import json, time, warnings, logging
import pandas as pd, numpy as np, yfinance as yf
from common import DATA

warnings.filterwarnings("ignore"); logging.getLogger("yfinance").setLevel(logging.CRITICAL)
PX = DATA / "prices"; PX.mkdir(exist_ok=True)
m = pd.read_csv(DATA / "meta.csv", parse_dates=["date"])
m = m[m.ipo_text & ~m.blank_check & ~m.units]
ct = json.load(open(DATA / "company_tickers.json"))
cur = {}
for v in ct.values():
    cur.setdefault(int(v["cik_str"]), v["ticker"])
mp_path = DATA / "price_map.csv"
done = pd.read_csv(mp_path) if mp_path.exists() else pd.DataFrame(columns=["acc", "ticker_used", "status", "first", "last"])
seen = set(done.acc)
out = []


def fetch(t, d0):
    h = yf.Ticker(t).history(start=(d0 - pd.Timedelta(days=10)).strftime("%Y-%m-%d"), auto_adjust=False, actions=True)
    if h is None or len(h) == 0:
        return None
    h.index = h.index.tz_localize(None).normalize()
    return h


for r in m.itertuples():
    if r.acc in seen:
        continue
    cands = [t for t in dict.fromkeys([r.ticker if isinstance(r.ticker, str) else None, cur.get(int(r.cik))]) if t]
    status, used, h = "no_ticker" if not cands else "no_data", None, None
    for t in cands:
        try:
            hh = fetch(t.replace(".", "-"), r.date)
        except Exception:
            hh = None
        time.sleep(0.25)
        if hh is None:
            continue
        lag = (hh.index[0] - r.date).days
        if -3 <= lag <= 20:
            status, used, h = "ok", t, hh
            break
        status = f"mismatch({lag}d)"
    if h is not None:
        spl = h["Stock Splits"].replace(0, 1.0)
        fut = spl[::-1].cumprod()[::-1].shift(-1).fillna(1.0)  # product of splits after each date
        adj = h["Adj Close"] if "Adj Close" in h else h["Close"]
        df = pd.DataFrame({"adj": adj, "close_unadj": h["Close"] * fut, "open_unadj": h["Open"] * fut,
                           "open": h["Open"] * adj / h["Close"], "volume": h["Volume"]})
        df.to_parquet(PX / f"{r.acc}.parquet")
    out.append(dict(acc=r.acc, ticker_used=used, status=status,
                    first=h.index[0].date() if h is not None else None, last=h.index[-1].date() if h is not None else None))
    if len(out) % 50 == 0:
        pd.concat([done, pd.DataFrame(out)]).to_csv(mp_path, index=False)
        print(len(out), r.date.date(), flush=True)
res = pd.concat([done, pd.DataFrame(out)])
res.to_csv(mp_path, index=False)
print(res.status.str.replace(r"\(.*", "", regex=True).value_counts())
