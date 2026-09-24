"""m03: convex trend following with long SPX calls, priced by Black-Scholes on a CBOE-index vol surface.

Data (cached in data/round5/m03_convex_trend_calls/):
  yf.csv            ^GSPC, ^SP500TR, ^IRX, SPY (close + adj close) from yfinance
  <NAME>_History.csv CBOE VIX, VIX3M, VIX6M, VIX1Y, SKEW

Timing: signal `up` is computed on close t (SPX total-return trend ensemble, 126/168/210/252 days).
The portfolio decision at close t uses up[t-1] (one full bar between signal and execution) and is
held from close t to close t+1.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import pathlib

import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA = ROOT / "data/round5/m03_convex_trend_calls"
TREND_LENGTHS = (126, 168, 210, 252)

# DEV-only term-structure mapping (fit on the 2007 overlap of VIX and VIX1Y, 249 days, DEV period):
#   VIX1Y ~= 6.152 + 0.6927 * VIX
V1Y_A, V1Y_B = 6.152, 0.6927
# 1-year call-wing skew slope (decimal vol per unit log-moneyness, times 1/sqrt(T)), measured from the
# 2026-09-23 SPX chain (ATM 17.5 -> 110% 14.6 at T=1y) when SKEW = 144.8. Scaled by (SKEW-100)/44.8.
SKEW_SLOPE_REF, SKEW_REF = -0.30, 144.8


def _cboe(name):
    x = pd.read_csv(DATA / f"{name}_History.csv")
    x.index = pd.to_datetime(x["DATE"], format="%m/%d/%Y")
    col = "CLOSE" if "CLOSE" in x else name
    return x[col].astype(float).rename(name)


def load_data():
    yf = pd.read_csv(DATA / "yf.csv", index_col=0, parse_dates=True)
    df = pd.DataFrame(index=yf["^GSPC_close"].dropna().index)
    df["spx"] = yf["^GSPC_close"]
    df["tr"] = yf["^SP500TR_close"]
    irx = yf["^IRX_close"].reindex(df.index).ffill() / 100.0
    # 13-week discount yield -> bond-equivalent (continuous-ish) annual rate
    df["r_ann"] = np.log1p(365 * irx / (360 - 91 * irx))
    df["rf_d"] = np.expm1(df["r_ann"] * df.index.to_series().diff().dt.days.fillna(1).values / 365.0)
    # SPY total return; before SPY existed (1993-01-29) use SP500TR less the 9.45bp expense ratio
    tr_ret = df["tr"].pct_change()
    spy_ret = yf["SPY_adj"].reindex(df.index).pct_change()
    df["spy_ret"] = spy_ret.where(yf["SPY_adj"].reindex(df.index).shift(1).notna(), tr_ret - 0.000945 / 252)
    # trailing 1-year dividend yield from TR vs price (known at t)
    div_d = tr_ret - df["spx"].pct_change()
    df["q"] = div_d.rolling(252, min_periods=200).sum().clip(0.0, 0.06)
    for n in ["VIX", "VIX3M", "VIX6M", "VIX1Y", "SKEW"]:
        df[n] = _cboe(n).reindex(df.index).ffill(limit=5)
    df["SKEW_s"] = df["SKEW"].rolling(20, min_periods=5).mean()
    lp = np.log(df["tr"])
    df["up"] = sum(((lp - lp.shift(L)) > 0).astype(float) for L in TREND_LENGTHS) / len(TREND_LENGTHS)
    df.loc[lp.shift(max(TREND_LENGTHS)).isna(), "up"] = np.nan
    return df


def term_vol(row, T, mode):
    """Variance-swap-style vol (decimal) at tenor T years from CBOE indices.
    mode 'model': VIX + DEV-fitted VIX1Y mapping only.  mode 'actual': all CBOE points available that day."""
    pts = [(30 / 365, row["VIX"])]
    if mode == "actual":
        for n, t in (("VIX3M", 91 / 365), ("VIX6M", 182 / 365)):
            if np.isfinite(row[n]):
                pts.append((t, row[n]))
        v1 = row["VIX1Y"] if np.isfinite(row["VIX1Y"]) else V1Y_A + V1Y_B * row["VIX"]
    else:
        v1 = V1Y_A + V1Y_B * row["VIX"]
    pts.append((1.0, v1))
    ts = np.array([p[0] for p in pts])
    w = np.array([(p[1] / 100.0) ** 2 * p[0] for p in pts])  # total variance
    T = np.atleast_1d(T).astype(float)
    Tc = np.clip(T, ts[0], None)
    tv = np.interp(Tc, ts, w)
    # beyond 1y: flat vol at 1y level; below 30d: flat at VIX
    tv = np.where(T > 1.0, w[-1] * T, tv)
    return np.sqrt(np.maximum(tv, 1e-10) / np.maximum(Tc, 1e-10))


def surface_iv(row, K, S, T, F, mode, vol_bump=0.0, atm_gap=0.0, slope_mult=1.0):
    """IV = var-swap level at T (+bump -gap) + skew slope * ln(K/F)/sqrt(T), clipped."""
    base = term_vol(row, T, mode) + vol_bump - atm_gap
    sk = row["SKEW_s"] if np.isfinite(row["SKEW_s"]) else 120.0
    slope = SKEW_SLOPE_REF * max(sk - 100.0, 0.0) / (SKEW_REF - 100.0) * slope_mult
    Te = np.maximum(T, 1 / 365)
    iv = base + slope * np.log(K / F) / np.sqrt(Te)
    return np.clip(iv, 0.4 * base, base + 0.25)


def bs_call(S, K, T, r, q, sig):
    T = np.maximum(T, 0.0)
    intrinsic = np.maximum(S - K, 0.0)
    sT = sig * np.sqrt(np.maximum(T, 1e-12))
    d1 = (np.log(S / K) + (r - q) * T + 0.5 * sT * sT) / sT
    d2 = d1 - sT
    px = S * np.exp(-q * T) * ndtr(d1) - K * np.exp(-r * T) * ndtr(d2)
    return np.where(T <= 1 / 365 / 4, intrinsic, px)


class Pricer:
    def __init__(self, mode="model", vol_bump=0.0, atm_gap=0.0, slope_mult=1.0, box_spread=0.005):
        self.mode, self.vol_bump, self.atm_gap = mode, vol_bump, atm_gap
        self.slope_mult, self.box_spread = slope_mult, box_spread

    def price(self, row, K, T):
        S = row["spx"]
        r = row["r_ann"] + self.box_spread  # SPX box rates sit above T-bills; higher r -> dearer calls
        q = row["q"] if np.isfinite(row["q"]) else 0.02
        F = S * np.exp((r - q) * np.asarray(T))
        iv = surface_iv(row, np.asarray(K, float), S, np.asarray(T, float), F, self.mode,
                        self.vol_bump, self.atm_gap, self.slope_mult)
        return bs_call(S, np.asarray(K, float), np.asarray(T, float), r, q, iv)


def backtest(df, start, end, X=0.2, m=1.0, R=3, T0=1.0, cost=0.02, pricer=None, binary=False):
    """Returns daily frame with nav, option weight, and a trade log.
    X: premium budget (fraction of NAV when fully 'up'); m: strike / spot at purchase;
    R: scheduled roll every R months (first trading day of month); cost: fraction of premium per trade."""
    pricer = pricer or Pricer()
    d = df.loc[start:end]
    dates = d.index
    up_lag = df["up"].shift(1).loc[start:end].to_numpy()  # decision at close t uses up[t-1]
    if binary:
        up_lag = (up_lag >= 0.5).astype(float)
    rows = d.to_dict("index")
    # scheduled roll days: first trading day of each month where month index % R == 0
    mon = dates.to_period("M")
    first_of_month = np.r_[True, mon[1:] != mon[:-1]]
    midx = (mon.year - mon[0].year) * 12 + (mon.month - mon[0].month)
    roll_day = first_of_month & (np.asarray(midx) % R == 0)
    roll_day[0] = True

    cash, lots = 1.0, []  # lot: [K, expiry_date, contracts]
    u_prev = 0.0
    out_nav, out_optw, out_cost, trades = [], [], [], []
    for i, t in enumerate(dates):
        row = rows[t]
        if i > 0:
            cash *= 1.0 + row["rf_d"]

        def lot_vals():
            if not lots:
                return np.zeros(0)
            K = np.array([l[0] for l in lots])
            T = np.array([(l[1] - t).days / 365.0 for l in lots])
            px = pricer.price(row, K, T)
            return px * np.array([l[2] for l in lots])

        vals = lot_vals()
        nav = cash + vals.sum()
        u = up_lag[i] if np.isfinite(up_lag[i]) else 0.0
        tcost = 0.0

        def sell_frac(frac):
            nonlocal cash, tcost, vals
            if not lots:
                return
            proceeds = vals.sum() * frac
            cash += proceeds * (1 - cost)
            tcost += proceeds * cost
            for l in lots:
                l[2] *= 1 - frac
            trades.append((t, "sell", proceeds))

        def buy_new(premium):
            nonlocal cash, tcost
            if premium <= 0:
                return
            K = m * row["spx"]
            exp = t + pd.Timedelta(days=int(round(T0 * 365)))
            px = float(pricer.price(row, np.array([K]), np.array([T0]))[0])
            n = premium / (px * (1 + cost))
            cash -= premium
            tcost += premium * cost / (1 + cost)
            lots.append([K, exp, n])
            trades.append((t, "buy", premium))

        expired = any((l[1] - t).days <= 0 for l in lots)
        if roll_day[i] or expired:
            if lots:
                sell_frac(1.0)
                lots.clear()
            if u > 0:
                buy_new(X * u * (cash))
        elif u != u_prev:
            if u == 0:
                sell_frac(1.0)
                lots.clear()
            elif u_prev == 0 or not lots:
                buy_new(X * u * nav)
            elif u < u_prev:
                sell_frac(1 - u / u_prev)
            else:  # scale up existing lots proportionally
                add = vals.sum() * (u / u_prev - 1)
                if add > 0 and vals.sum() > 0:
                    f = add / vals.sum()
                    cash -= add * (1 + cost)
                    tcost += add * cost
                    for l in lots:
                        l[2] *= 1 + f
                    trades.append((t, "add", add))
        u_prev = u
        vals = lot_vals()
        nav = cash + vals.sum()
        out_nav.append(nav)
        out_optw.append(vals.sum() / nav if nav > 0 else 0)
        out_cost.append(tcost)
    res = pd.DataFrame({"nav": out_nav, "optw": out_optw, "cost": out_cost}, index=dates)
    res["ret"] = res["nav"].pct_change().fillna(0.0)
    return res, pd.DataFrame(trades, columns=["date", "side", "premium"])


def benchmarks(df, start, end, spy_cost=0.0002):
    d = df.loc[start:end]
    w = df["up"].shift(1).reindex(df.index)  # decision at close t uses up[t-1] ...
    w_held = w.shift(1).loc[start:end].fillna(0.0)  # ... and earns return of t+1
    spy = d["spy_ret"].fillna(0.0)
    rf = d["rf_d"].fillna(0.0)
    turn = w_held.diff().abs().fillna(w_held.iloc[0])
    trend = w_held * spy + (1 - w_held) * rf - turn * spy_cost
    spy.iloc[0] = 0.0
    trend.iloc[0] = 0.0
    return pd.DataFrame({"spy": spy, "trend_spy": trend, "rf": rf, "w_trend": w_held})


def stats(r, rf=None):
    r = r.fillna(0.0)
    nav = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    ex = r - (rf if rf is not None else 0.0)
    sharpe = ex.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    dd = (nav / nav.cummax() - 1).min()
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd)


def yearly(r):
    return (1 + r.fillna(0)).groupby(r.index.year).prod() - 1


def beta(r, b):
    c = np.cov(r.fillna(0), b.fillna(0))
    return c[0, 1] / c[1, 1]
