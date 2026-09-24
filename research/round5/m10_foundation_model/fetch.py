"""Fetch data for m10 (foundation-model forecasting).
Outputs (data/round5/m10_foundation_model/):
  sp500_wiki.html          Wikipedia S&P 500 page (current members + change log)
  members.csv              current members, plus members as of 2025-01-01 reconstructed from change log
  px_stocks.parquet        adjusted close, current S&P 500 members + names removed since 2025-01-01 (if on yfinance)
  px_etf.parquet           adjusted close, ETF universe (tickers from data/etf_universe_meta.csv)
  px_crypto.parquet        close, top-cap cryptos as of end-2024 (ex stablecoins), 7-day calendar
"""
import os, io, time, urllib.request
import pandas as pd
import yfinance as yf

D = "/home/user/alpha/data/round5/m10_foundation_model"
START, END = "2021-06-01", "2026-09-25"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "alpha-research contact@alpha-research.dev"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def members():
    f = f"{D}/sp500_wiki.html"
    if not os.path.exists(f):
        open(f, "w").write(get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"))
    tabs = pd.read_html(io.StringIO(open(f).read()))
    cur = tabs[0]
    f2 = f"{D}/sp500_hist.html"
    if not os.path.exists(f2):
        open(f2, "w").write(get("https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"))
    ch = pd.read_html(io.StringIO(open(f2).read()))[0]
    ch.columns = ["_".join([c for c in col if c]) if isinstance(col, tuple) else col for col in ch.columns]
    cur_syms = set(cur["Symbol"].str.replace(".", "-", regex=False))
    # walk change log backwards to 2025-01-01
    datecol = [c for c in ch.columns if "Date" in c][0]
    addcol = [c for c in ch.columns if c.startswith("Added") and "Ticker" in c][0]
    remcol = [c for c in ch.columns if c.startswith("Removed") and "Ticker" in c][0]
    ch["date"] = pd.to_datetime(ch[datecol], errors="coerce")
    post = ch[ch["date"] >= "2025-01-01"]
    added = set(post[addcol].dropna().astype(str).str.replace(".", "-", regex=False))
    removed = set(post[remcol].dropna().astype(str).str.replace(".", "-", regex=False))
    m2025 = (cur_syms - added) | removed
    post[["date", addcol, remcol]].to_csv(f"{D}/changes_since_2025.csv", index=False)
    rows = [(s, s in cur_syms, s in m2025) for s in sorted(cur_syms | m2025)]
    df = pd.DataFrame(rows, columns=["ticker", "current", "member_2025_01_01"])
    df.to_csv(f"{D}/members.csv", index=False)
    print(len(cur_syms), "current;", len(m2025), "as of 2025-01-01;", len(added), "added;", len(removed), "removed")
    return df


def dl(tickers, out):
    if os.path.exists(out):
        return pd.read_parquet(out)
    frames = []
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        x = yf.download(chunk, start=START, end=END, auto_adjust=True, progress=False, threads=False)["Close"]
        if isinstance(x, pd.Series):
            x = x.to_frame(chunk[0])
        frames.append(x)
        time.sleep(1)
    px = pd.concat(frames, axis=1)
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px.loc[:, px.notna().sum() > 0]
    px.to_parquet(out)
    print(out, px.shape, px.index.min(), px.index.max())
    return px


CRYPTO = ["BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "BNB-USD", "DOGE-USD", "ADA-USD", "TRX-USD",
          "AVAX-USD", "LINK-USD", "SHIB-USD", "TON11419-USD", "XLM-USD", "SUI20947-USD", "DOT-USD",
          "HBAR-USD", "BCH-USD", "LTC-USD", "UNI7083-USD", "PEPE24478-USD", "NEAR-USD", "APT21794-USD",
          "ICP-USD", "ETC-USD", "POL28321-USD", "RENDER-USD", "VET-USD", "FIL-USD", "ATOM-USD",
          "ALGO-USD", "AAVE-USD", "ARB11841-USD", "OP-USD", "INJ-USD", "STX4847-USD", "TAO22974-USD"]

if __name__ == "__main__":
    m = members()
    dl(sorted(m.ticker), f"{D}/px_stocks.parquet")
    etfs = pd.read_csv("/home/user/alpha/data/etf_universe_meta.csv").ticker.tolist()
    dl(etfs, f"{D}/px_etf.parquet")
    dl(CRYPTO, f"{D}/px_crypto.parquet")
