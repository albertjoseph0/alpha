"""Shared backtest engine for m09 (daily, spot, long-only, cash otherwise).

Weight convention: W.loc[t] = target weights decided with data up to the close of day t-1 and
executed at the close of day t (one full bar of lag). Portfolio return on day t+1 = W.loc[t] . r[t+1].
Callers build a signal S.loc[d] from day-d data and pass W = f(S).shift(1).

Costs per side = 10 bp taker fee + half-spread/slippage tier by trailing 30-day median quote volume:
  >= $200M: 2 bp | $50-200M: 5 bp | $10-50M: 10 bp | $2-10M: 25 bp | < $2M: 50 bp.
Delisting / data end / gap: if a held coin has no return on day t+1 (its life ended), the position is
closed at its last close minus a haircut (default 0; sensitivity 50%) and the cash is kept.
"""
import numpy as np
import pandas as pd

D = "/home/user/alpha/data/round5/m09_crypto_flow"
FEE = 0.0010
DEV = ("2020-01-01", "2022-12-31")
TEST = ("2023-01-01", "2026-12-31")


def tier_cost(adv):
    c = np.select([adv >= 200e6, adv >= 50e6, adv >= 10e6, adv >= 2e6], [2, 5, 10, 25], 50) / 1e4
    return pd.DataFrame(c, index=adv.index, columns=adv.columns).where(adv.notna(), 50 / 1e4)


def load_wide(cols=("ret", "close", "adv30", "fund8", "fund_day", "tb_share", "age", "qvol", "is_last"),
              cap="2022-12-31"):
    """cap: last date loaded. DEV work uses the default cap so TEST data is physically absent."""
    p = pd.read_parquet(f"{D}/panel.parquet")
    if cap is not None:
        p = p[p.date <= cap]
    out = {}
    for c in cols:
        out[c] = p.pivot(index="date", columns="sid", values=c).sort_index()
    idx = pd.date_range(out["ret"].index.min(), out["ret"].index.max(), freq="D")
    out = {k: v.reindex(idx) for k, v in out.items()}
    return out, p


def backtest(W, R, ADV, cost_mult=1.0, haircut=0.0, start=None, end=None):
    """W: target weights (index=date t, executed at close t). R: daily returns (NaN = no trade that day).
    Returns daily net returns series (index = day of return) and stats dict."""
    W = W.reindex(R.index).fillna(0.0)
    if start is not None:
        W = W.loc[start:end]
    idx = W.index
    Rn = R.reindex(idx)
    C = tier_cost(ADV.reindex(idx)) + FEE
    C = C * cost_mult
    cols = W.columns
    w_prev = pd.Series(0.0, index=cols)
    rets, turns, costs = [], [], []
    Wv, Rv, Cv = W.values, Rn.shift(-1).values, C.values  # Rv[t] = return from close t to close t+1
    wp = np.zeros(len(cols))
    for i in range(len(idx)):
        tgt = Wv[i]
        # a coin with no next-day return cannot be (re)bought: its life ended / no trading
        nxt = Rv[i]
        tradable = ~np.isnan(nxt)
        tgt = np.where(tradable, tgt, 0.0)
        # positions held in a coin whose data ends: forced exit at last close minus haircut
        forced = (wp > 0) & ~tradable
        hc = (wp[forced] * haircut).sum()
        trade = np.abs(tgt - wp)
        cost = np.nansum(trade * Cv[i]) + hc
        r = np.nansum(tgt * np.where(tradable, nxt, 0.0))
        net = (1 - cost) * (1 + r) - 1 if True else r
        rets.append(net)
        turns.append(trade.sum())
        costs.append(cost)
        # drift
        gross = tgt * (1 + np.where(tradable, nxt, 0.0))
        tot = 1 + r
        wp = gross / tot if tot > 0 else np.zeros_like(gross)
    s = pd.Series(rets, index=idx + pd.Timedelta(days=1))
    return s, pd.Series(turns, index=idx), pd.Series(costs, index=idx)


def stats(r, label=""):
    r = r.dropna()
    if len(r) == 0:
        return {}
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25 + 1 / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    vol = r.std() * np.sqrt(365)
    return {"label": label, "cagr": cagr, "maxdd": dd, "vol": vol,
            "sharpe": r.mean() * 365 / vol if vol > 0 else np.nan, "start": r.index[0].date(),
            "end": r.index[-1].date()}


def btc_returns(wide):
    c = [s for s in wide["ret"].columns if s.startswith("BTCUSDT#")]
    return wide["ret"][c[0]]


def spy_returns():
    e = pd.read_csv("/home/user/alpha/data/etf_universe_daily.csv", usecols=["date", "SPY"], parse_dates=["date"])
    return e.set_index("date").SPY.dropna()


def cagr_between(r, start, end):
    r = r.loc[start:end].dropna()
    eq = (1 + r).prod()
    yrs = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    return eq ** (1 / yrs) - 1


def yearly(r):
    return (1 + r).groupby(r.index.year).prod() - 1
