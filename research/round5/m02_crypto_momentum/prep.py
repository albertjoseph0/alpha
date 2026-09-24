"""Build point-in-time panel from raw Binance *USDT daily klines.

- Excludes stablecoin / fiat / gold-token bases and leveraged tokens (*UP/*DOWN/*BULL/*BEAR).
- Splits a symbol's history into separate "instruments" at gaps > GAP_DAYS (symbol reuse, e.g.
  LUNAUSDT = Terra Classic until 2022-05, then Terra 2.0 from 2022-05-31). Each instrument ends
  at its last traded day; the backtest treats that as a delisting.
- Output: wide parquet tables (date x instrument): close, qv (quote volume, USDT), trades.
"""
import pandas as pd, numpy as np

D = "/home/user/alpha/data/round5/m02_crypto_momentum"
GAP_DAYS = 7

STABLE_FIAT = {
    "USDC", "BUSD", "TUSD", "PAX", "USDP", "USDS", "USDSB", "DAI", "FDUSD", "UST", "USTC", "SUSD",
    "EUR", "GBP", "AUD", "BRL", "TRY", "RUB", "UAH", "NGN", "ZAR", "BIDR", "IDRT", "BVND", "BKRW",
    "PAXG", "XAUT", "AEUR", "EURI", "USD1", "RLUSD", "USDE", "BFUSD", "XUSD", "USDF", "TUSDB", "JPY",
    "MXN", "ARS", "COP", "PLN", "RON", "CZK", "USDQ", "GUSD", "PYUSD", "FRAX", "LUSD", "USDD",
}


def leveraged(base, bases):
    for suf in ("UP", "DOWN", "BULL", "BEAR"):
        if base.endswith(suf) and len(base) > len(suf):
            stem = base[: -len(suf)]
            if stem in bases or stem in ("BTC", "ETH", "BNB", "XRP", "EOS", "TRX", "LINK", "XTZ", "ADA"):
                return True
    return False


def main():
    k = pd.read_parquet(f"{D}/klines_1d.parquet")
    k["base"] = k.symbol.str[:-4]
    bases = set(k.base)
    lev = sorted(b for b in bases if leveraged(b, bases))
    stab = sorted(b for b in bases if b in STABLE_FIAT)
    print("leveraged tokens excluded:", len(lev), lev[:40])
    print("stable/fiat/gold excluded:", stab)
    k = k[~k.base.isin(set(lev) | set(stab))].copy()
    k = k[k.close > 0]
    # segment at gaps
    k = k.sort_values(["symbol", "date"])
    gap = k.groupby("symbol").date.diff().dt.days
    seg = (gap > GAP_DAYS).astype(int).groupby(k.symbol).cumsum()
    k["inst"] = k.symbol + np.where(seg > 0, "#" + seg.astype(str), "")
    multi = k[seg > 0].symbol.unique()
    print("symbols split at gaps >%dd:" % GAP_DAYS, len(multi), list(multi)[:30])
    idx = pd.date_range(k.date.min(), k.date.max(), freq="D")
    wide = {}
    for col in ["close", "quote_volume", "trades"]:
        w = k.pivot(index="date", columns="inst", values=col).reindex(idx)
        wide[col] = w
    close = wide["close"]
    # forward-fill price only inside each instrument's live span (short gaps -> zero return)
    first = close.apply(lambda s: s.first_valid_index())
    last = close.apply(lambda s: s.last_valid_index())
    live = pd.DataFrame(False, index=idx, columns=close.columns)
    for c in close.columns:
        live.loc[first[c]:last[c], c] = True
    close = close.ffill().where(live)
    qv = wide["quote_volume"].fillna(0).where(live)
    tr = wide["trades"].fillna(0).where(live)
    close.to_parquet(f"{D}/close.parquet"); qv.to_parquet(f"{D}/qv.parquet"); tr.to_parquet(f"{D}/trades.parquet")
    meta = pd.DataFrame({"first": first, "last": last})
    meta["symbol"] = meta.index.str.split("#").str[0]
    meta.to_csv(f"{D}/instruments.csv")
    end = idx[-1]
    dl = meta[meta["last"] < end - pd.Timedelta(days=3)]
    print(f"{len(meta)} instruments, {len(dl)} ended before {end.date()} (delisted/renamed)")
    for s in ["LUNAUSDT", "LUNAUSDT#1", "FTTUSDT", "BCCUSDT", "VENUSDT", "NPXSUSDT", "BTTUSDT", "SRMUSDT"]:
        if s in meta.index:
            print(s, meta.loc[s, "first"].date(), meta.loc[s, "last"].date(), "last close", close[s].dropna().iloc[-1])
    # extreme daily moves (possible redenominations)
    r = close.pct_change(fill_method=None)
    ext = r.stack()
    ext = ext[(ext > 3) | (ext < -0.8)]
    print("extreme daily moves (>+300% or <-80%):")
    print(ext.sort_values().to_string())


if __name__ == "__main__":
    main()
