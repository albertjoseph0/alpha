"""Tradeable universe v2: US-listed ETFs across asset classes (round 3).

Rules (fixed before any strategy research):
  * one fund per exposure (no near-duplicates);
  * liquid, US-listed, no leverage, no inverse funds, no single stocks;
  * defined downside: every instrument's worst case is losing the amount invested;
  * option-strategy ETFs included (covered call / buy-write).
Outputs:
  data/etf_universe_daily.csv  simple daily total returns (dividend-adjusted), NaN before inception
  data/etf_universe_meta.csv   ticker, asset class, description, inception, avg $ volume, cost_bps
Trading cost per ETF = half-spread + impact tier from its trailing-year average dollar volume:
  >= $1B/day: 2 bp;  >= $100M: 4 bp;  >= $10M: 10 bp;  else 25 bp.
Caveats: survivorship (closed funds are missing); yfinance adjusted closes.

Usage: python data/fetch_etf_universe.py
"""
from __future__ import annotations

import pathlib
import time

import pandas as pd
import yfinance as yf

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "etf_universe_daily.csv"
META = HERE / "etf_universe_meta.csv"

UNIVERSE = {
    # --- US equity: broad, size, style, factor
    "SPY": ("us_equity", "S&P 500"), "QQQ": ("us_equity", "Nasdaq-100"),
    "MDY": ("us_equity", "S&P MidCap 400"), "IWM": ("us_equity", "Russell 2000"),
    "IWD": ("us_equity", "Russell 1000 Value"), "IWF": ("us_equity", "Russell 1000 Growth"),
    "USMV": ("us_equity", "US min volatility"), "MTUM": ("us_equity", "US momentum factor"),
    # --- US sectors (Select Sector SPDRs)
    "XLB": ("sector", "Materials"), "XLE": ("sector", "Energy"), "XLF": ("sector", "Financials"),
    "XLI": ("sector", "Industrials"), "XLK": ("sector", "Technology"), "XLP": ("sector", "Consumer staples"),
    "XLU": ("sector", "Utilities"), "XLV": ("sector", "Health care"), "XLY": ("sector", "Consumer discretionary"),
    "XLRE": ("sector", "Real estate"), "XLC": ("sector", "Communication services"),
    # --- US industries (distinct from the sectors)
    "SOXX": ("industry", "Semiconductors"), "IBB": ("industry", "Biotech"), "ITB": ("industry", "Homebuilders"),
    "KRE": ("industry", "Regional banks"), "XME": ("industry", "Metals & mining"), "GDX": ("industry", "Gold miners"),
    "IGV": ("industry", "Software"), "ITA": ("industry", "Aerospace & defense"),
    # --- International equity
    "EFA": ("intl_equity", "Developed ex-US"), "EEM": ("intl_equity", "Emerging markets"),
    "EWJ": ("intl_equity", "Japan"), "VGK": ("intl_equity", "Europe"), "EWZ": ("intl_equity", "Brazil"),
    "FXI": ("intl_equity", "China large-cap"), "INDA": ("intl_equity", "India"), "EWC": ("intl_equity", "Canada"),
    "EWA": ("intl_equity", "Australia"),
    # --- Bonds
    "SHY": ("bond", "Treasury 1-3y"), "IEF": ("bond", "Treasury 7-10y"), "TLT": ("bond", "Treasury 20y+"),
    "TIP": ("bond", "TIPS"), "LQD": ("bond", "IG corporate"), "HYG": ("bond", "High yield"),
    "EMB": ("bond", "EM USD bonds"), "MUB": ("bond", "Municipal"), "BWX": ("bond", "Intl Treasury"),
    # --- Real assets
    "GLD": ("real_asset", "Gold"), "SLV": ("real_asset", "Silver"), "DBC": ("real_asset", "Broad commodities"),
    "DBA": ("real_asset", "Agriculture"), "VNQ": ("real_asset", "US REITs"), "UUP": ("real_asset", "US dollar index"),
    # --- Option-strategy ETFs (defined risk: covered calls / buy-write)
    "PBP": ("options", "S&P 500 BuyWrite (covered call)"), "XYLD": ("options", "S&P 500 covered call"),
    "QYLD": ("options", "Nasdaq-100 covered call"), "JEPI": ("options", "Equity premium income"),
    # --- Volatility (long only, 1x)
    "VIXY": ("volatility", "Short-term VIX futures (long vol)"),
}


def _tier(dollar_vol: float) -> float:
    if dollar_vol >= 1e9:
        return 2.0
    if dollar_vol >= 1e8:
        return 4.0
    if dollar_vol >= 1e7:
        return 10.0
    return 25.0


def main() -> None:
    closes, meta = {}, []
    for t, (cls, desc) in UNIVERSE.items():
        d = None
        for attempt in range(4):
            try:
                d = yf.download(t, period="max", auto_adjust=True, progress=False)
                if len(d):
                    break
            except Exception as e:
                print(f"{t}: {e}")
            time.sleep(2 ** attempt)
        if d is None or not len(d):
            print(f"{t}: FAILED")
            continue
        c = d["Close"].squeeze()
        v = d["Volume"].squeeze()
        closes[t] = c
        dv = float((c * v).iloc[-252:].mean())
        meta.append(dict(ticker=t, asset_class=cls, description=desc, inception=str(c.index[0].date()),
                         avg_dollar_volume=round(dv), cost_bps=_tier(dv)))
        print(f"{t:5s} {cls:12s} {str(c.index[0].date())}  ${dv/1e6:,.0f}M/day  {_tier(dv)}bp", flush=True)
        time.sleep(0.5)
    px = pd.DataFrame(closes).sort_index()
    rets = px.pct_change(fill_method=None).iloc[1:]
    rets.index.name = "date"
    rets.to_csv(OUT, float_format="%.8f")
    pd.DataFrame(meta).to_csv(META, index=False)
    print(f"wrote {OUT} {rets.shape} and {META}")


if __name__ == "__main__":
    main()
