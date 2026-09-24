"""m01 shared loaders: Ken French momentum portfolios, market/RF, trend regime, ETF defense sleeve."""
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "round5" / "m01_midcap_momentum"
OUT = pathlib.Path(__file__).resolve().parent
TREND_LENGTHS = (126, 168, 210, 252)


def read_french_section(fname, title, freq="M"):
    """Read one section (identified by a substring of its title line) of a French CSV."""
    lines = open(DATA / fname).read().splitlines()
    i = next(k for k, l in enumerate(lines) if title.lower() in l.lower())
    header = lines[i + 1].split(",")
    rows = []
    for l in lines[i + 2:]:
        if not l.strip() or not l.strip()[0].isdigit():
            break
        p = [x.strip() for x in l.split(",")]
        rows.append(p)
    df = pd.DataFrame(rows, columns=["date"] + [h.strip() for h in header[1:]])
    if freq == "M":
        df["date"] = pd.to_datetime(df["date"], format="%Y%m") + pd.offsets.MonthEnd(0)
    else:
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.set_index("date").astype(float)
    df = df.mask(df <= -99.99)
    return df


def french_25_monthly(kind="vw"):
    t = {"vw": "Average Value Weighted Returns -- Monthly", "ew": "Average Equal Weighted Returns -- Monthly",
         "n": "Number of Firms", "size": "Average Market Cap"}[kind]
    df = read_french_section("25_Portfolios_ME_Prior_12_2.csv", t)
    df.columns = [c.replace("SMALL LoPRIOR", "ME1 PRIOR1").replace("SMALL HiPRIOR", "ME1 PRIOR5")
                  .replace("BIG LoPRIOR", "ME5 PRIOR1").replace("BIG HiPRIOR", "ME5 PRIOR5") for c in df.columns]
    return df / 100.0 if kind in ("vw", "ew") else df


def french_10_monthly(kind="vw"):
    t = {"vw": "Value Weight Returns -- Monthly", "ew": "Average Equal Weighted Returns -- Monthly",
         "n": "Number of Firms"}[kind]
    df = read_french_section("10_Portfolios_Prior_12_2.csv", t)
    return df / 100.0 if kind in ("vw", "ew") else df


def market_daily():
    m = pd.read_csv(ROOT / "data" / "market_daily.csv", parse_dates=["date"], index_col="date")
    return m[["Mkt", "RF"]]


def trend_regime_monthly(daily_ret: pd.Series) -> pd.Series:
    """Fraction of the 4 trend signals (126/168/210/252-day total return > 0) that are up,
    evaluated at the close of the PENULTIMATE trading day of each month (1-day execution lag:
    trade at the last close of the month, earn next month's return). Indexed by month-end of the
    month in which the signal is formed; apply to the NEXT month's return."""
    lp = np.log1p(daily_ret.fillna(0.0)).cumsum()
    up = sum(((lp - lp.shift(L)) > 0).astype(float) for L in TREND_LENGTHS) / len(TREND_LENGTHS)
    valid = lp.index >= lp.index[max(TREND_LENGTHS)]
    up = up[valid]
    ym = up.index.to_period("M")
    # penultimate trading day of each month
    pen = up.groupby(ym).apply(lambda s: s.iloc[-2] if len(s) >= 2 else np.nan)
    pen.index = pen.index.to_timestamp(how="end").normalize()
    return pen


def etf_data():
    R = pd.read_csv(ROOT / "data" / "etf_universe_daily.csv", parse_dates=["date"], index_col="date")
    meta = pd.read_csv(ROOT / "data" / "etf_universe_meta.csv", index_col="ticker")
    return R, meta


def defense_sleeve_daily(cost_mult=1.0):
    """Daily returns of the deep_trend_switch DEFENSE sleeve (Sharpe momentum top 7, 4 staggered
    tranches, VIXY excluded), with per-ETF costs from etf_universe_meta, 1-day lag
    (weights decided at close t, traded at close t+1, earning from t+2)."""
    cache = DATA / f"defense_daily_x{cost_mult:g}.csv"
    if cache.exists():
        return pd.read_csv(cache, parse_dates=["date"], index_col="date").iloc[:, 0]
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "strategies" / "r3_options"))
    from strategy import MomentumSleeve
    R, meta = etf_data()

    class D:  # minimal MarketData stand-in
        returns = R
        dates = R.index
    sl = MomentumSleeve("sharpe", 7, "eq", (0, 5, 10, 15), ("VIXY",))
    W = sl.predict(D, R.index).ffill().fillna(0.0)
    cost = meta["cost_bps"].reindex(R.columns).fillna(5.0).values / 1e4 * cost_mult
    Rv = R.fillna(0.0).values
    Wt = W.shift(1).values  # target decided at t-1 close, held from t close -> earns from t+1
    Wt = np.nan_to_num(Wt)
    out = np.zeros(len(R))
    h = np.zeros(R.shape[1])
    for i in range(len(R)):
        # earn return on current holdings
        g = h * (1 + Rv[i])
        port = h.sum()
        r = (g.sum() - port) if port > 0 else 0.0
        out[i] = r
        tot = g.sum()
        h = g / tot if tot > 0 else g
        # trade at close i to target decided at close i-1
        tgt = Wt[i]
        if tgt.sum() > 0:
            tc = (np.abs(tgt - h) * cost).sum()
            out[i] -= tc
            h = tgt.copy()
    s = pd.Series(out, index=R.index, name="defense")
    s.to_frame().to_csv(cache)
    return s


def monthly(r: pd.Series) -> pd.Series:
    return (1 + r).groupby(r.index.to_period("M")).prod().pipe(
        lambda x: x.set_axis(x.index.to_timestamp(how="end").normalize())) - 1


def cagr(r: pd.Series, periods=12):
    r = r.dropna()
    return (1 + r).prod() ** (periods / len(r)) - 1


def maxdd(r: pd.Series):
    eq = (1 + r.dropna()).cumprod()
    return (eq / eq.cummax() - 1).min()
