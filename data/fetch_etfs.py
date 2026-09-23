"""Download daily total-return (dividend-adjusted) closes for US industry ETFs via yfinance.

One ETF per industry (no near-duplicates such as XLK/IYW/VGT), chosen to mirror the
49-industry idea with instruments that are actually tradeable. Writes
data/etf_daily.csv: simple daily returns, NaN before each ETF's inception.

Caveat: the list is of ETFs that exist today (survivorship bias).

Usage: python data/fetch_etfs.py
"""
from __future__ import annotations

import pathlib
import time

import pandas as pd
import yfinance as yf

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "etf_daily.csv"

UNIVERSE = {
    # Select Sector SPDRs (Dec 1998)
    "XLB": "Materials", "XLE": "Energy", "XLF": "Financials", "XLI": "Industrials",
    "XLK": "Technology", "XLP": "Consumer staples", "XLU": "Utilities",
    "XLV": "Health care", "XLY": "Consumer discretionary",
    # iShares US sector/industry (2000-2003)
    "IYR": "Real estate", "IYZ": "Telecom", "IYT": "Transportation", "IYG": "Financial services",
    "IBB": "Biotech", "SOXX": "Semiconductors", "IGV": "Software",
    # 2005-2006 industry wave
    "ITA": "Aerospace & defense", "ITB": "Homebuilders", "IHI": "Medical devices",
    "IHF": "Healthcare providers", "IHE": "Pharmaceuticals", "IAI": "Broker-dealers",
    "IAK": "Insurance", "KRE": "Regional banks", "KBE": "Banks", "IEO": "Oil & gas E&P",
    "IEZ": "Oil equipment & services", "XME": "Metals & mining", "XRT": "Retail",
    "GDX": "Gold miners", "PBJ": "Food & beverage", "PEJ": "Leisure & entertainment",
    "PBS": "Media", "PKB": "Building & construction", "PHO": "Water", "SLX": "Steel",
    # later
    "TAN": "Solar", "BJK": "Gaming", "SKYY": "Cloud computing", "JETS": "Airlines",
    "HACK": "Cybersecurity",
}
BENCH = ["SPY"]


def fetch(tickers: list[str]) -> pd.DataFrame:
    closes = {}
    for t in tickers:
        for attempt in range(4):
            try:
                d = yf.download(t, period="max", auto_adjust=True, progress=False)
                if len(d):
                    closes[t] = d["Close"].squeeze()
                    break
            except Exception as e:  # rate limits: back off and retry
                print(f"{t}: {e}")
            time.sleep(2 ** attempt)
        print(f"{t}: {len(closes.get(t, [])) } rows", flush=True)
        time.sleep(0.5)
    px = pd.DataFrame(closes).sort_index()
    rets = px.pct_change(fill_method=None)
    rets.index.name = "date"
    return rets


if __name__ == "__main__":
    r = fetch(list(UNIVERSE) + BENCH)
    r.to_csv(OUT, float_format="%.8f")
    first = r.apply(lambda c: c.first_valid_index())
    print(f"wrote {OUT}: {r.shape}, {r.index[0].date()} -> {r.index[-1].date()}")
    print(first.dt.year.value_counts().sort_index().to_string())
