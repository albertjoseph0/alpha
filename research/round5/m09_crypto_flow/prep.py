"""Build the daily point-in-time panel used by every m09 test.

Timestamp conventions (all UTC):
* spot 1d kline for date D covers [D 00:00, D+1 00:00); close = price at D+1 00:00 (end of day D).
* funding settlement with calc_time T (ms). It is published at T. We floor T to the hour
  (the archive has a few ms of jitter, e.g. ...200002) and assign it to the UTC date of T.
  So day D's funding = settlements at D 00:00, 08:00, 16:00 (or more for 4h/1h intervals); all are
  public by D 16:00, before day D's close. A settlement at D+1 00:00 belongs to D+1.
* Every strategy forms a signal from day<=D data and trades at the close of D+1 (one full bar lag),
  so the first return it earns is close(D+1)->close(D+2).

Output: data/round5/m09_crypto_flow/panel.parquet with one row per (spot symbol, date).
"""
import re
import numpy as np
import pandas as pd

D = "/home/user/alpha/data/round5/m09_crypto_flow"
STABLE = {"USDC", "BUSD", "TUSD", "USDP", "PAX", "DAI", "FDUSD", "USDS", "SUSD", "UST", "USTC", "EUR",
          "GBP", "AUD", "BRL", "TRY", "USDSB", "XUSD", "USD1", "BFUSD", "RLUSD", "AEUR", "EURI", "USDE", "PAXG"}


def base_of(sym):
    return sym[:-4] if sym.endswith("USDT") else None


def is_leveraged(base, bases):
    for suf in ("UP", "DOWN", "BULL", "BEAR"):
        if base.endswith(suf) and base[: -len(suf)] in bases and len(base) > len(suf) + 1:
            return True
    return base in ("BULL", "BEAR")


def perp_to_spot(p):
    """USDT-M perp symbol -> spot symbol (strip 1000/1000000/1M multipliers)."""
    if not p.endswith("USDT"):
        return None, 1.0
    b = p[:-4]
    mult = 1.0
    for pre, m in (("1000000", 1e6), ("1000", 1e3), ("1M", 1e6)):
        if b.startswith(pre) and len(b) > len(pre):
            b, mult = b[len(pre):], m
            break
    if b == "LUNA2":
        b = "LUNA"
    return b + "USDT", mult


def build():
    spot = pd.read_parquet(f"{D}/spot_1d.parquet")
    spot = spot[spot.symbol.str.endswith("USDT")].copy()
    spot["base"] = spot.symbol.str[:-4]
    bases = set(spot.base)
    bad = {b for b in bases if b in STABLE or is_leveraged(b, bases)}
    spot = spot[~spot.base.isin(bad)].copy()
    spot = spot.sort_values(["symbol", "date"]).reset_index(drop=True)

    # --- "lives": split a symbol's history at gaps > 3 days (delist/relist, ticker reuse) ---
    gap = spot.groupby("symbol").date.diff().dt.days
    spot["life"] = (gap.isna() | (gap > 3)).astype(int).groupby(spot.symbol).cumsum()
    spot["sid"] = spot.symbol + "#" + spot.life.astype(str)
    prev_close = spot.groupby("sid").close.shift(1)
    consecutive = spot.groupby("sid").date.diff().dt.days == 1
    spot["ret"] = np.where(consecutive, spot.close / prev_close - 1, np.nan)
    spot["age"] = spot.groupby("sid").cumcount()  # days since first kline of this life
    spot["tb_share"] = np.where(spot.qvol > 0, spot.tb_quote / spot.qvol, np.nan)
    spot["adv30"] = spot.groupby("sid").qvol.transform(lambda s: s.rolling(30, min_periods=10).median())
    last_date = spot.groupby("sid").date.transform("max")
    spot["is_last"] = spot.date == last_date

    # --- funding, per-day aggregation ---
    f = pd.read_parquet(f"{D}/funding.parquet")
    m = f.symbol.map(lambda p: perp_to_spot(p)[0])
    f["spot"] = m
    f = f[f.spot.notna()]
    t = pd.to_datetime((f.calc_time // 3_600_000) * 3_600_000, unit="ms")
    f["date"] = t.dt.normalize()
    f["interval_h"] = f.interval_h.fillna(8).replace(0, 8)
    f["rate8h"] = f.rate * 8.0 / f.interval_h
    # if two perps map to the same spot (e.g. XUSDT and 1000XUSDT) keep the older contract
    first = f.groupby(["spot", "symbol"]).date.min().reset_index().sort_values("date")
    keep = first.drop_duplicates(["spot", "date"], keep="first")
    fd = (f.groupby(["spot", "date"]).agg(fund_day=("rate", "sum"), fund8=("rate8h", "mean"),
                                          n_settle=("rate", "size")).reset_index()
          .rename(columns={"spot": "symbol"}))
    panel = spot.merge(fd, on=["symbol", "date"], how="left")
    panel = panel.drop(columns=["life"])
    panel.to_parquet(f"{D}/panel.parquet", index=False)
    print(panel.shape, panel.symbol.nunique(), panel.sid.nunique(),
          "with funding:", panel.dropna(subset=["fund8"]).symbol.nunique(),
          panel.date.min(), panel.date.max())
    print("excluded bases:", sorted(bad)[:80])


if __name__ == "__main__":
    build()
