"""Long-only cross-sectional crypto momentum with a BTC trend filter (Binance spot, USDT pairs).

Timing (1-bar lag): signal at the close of day t (UTC daily bar) uses data <= t; the trade is
executed at the close of t+1; the new weights earn returns from t+2 onward.

Universe at t: instruments live at t, with >= MIN_AGE days of history, ranked by trailing
LIQ_WIN-day mean quote volume (USDT) over days <= t; keep the top N_UNIV.
Stablecoins/fiat/leveraged tokens are removed in prep.py.

Delisting: an instrument whose data ends while held is either sold at its last close (mode
"last", paying costs) or written off to zero (mode "zero").

Costs per side, as a fraction of traded value:
    fee 10 bp  +  spread/slippage  s(ADV) = clip(3 + 30/sqrt(ADV in $M), 3, 150) bp
    [+ optional square-root impact  IMPACT_Y * sigma_daily * sqrt(order $ / ADV $) for capacity]
ADV = trailing 30-day mean quote volume up to the signal day.
Cash (USDT) earns 0.
"""
import numpy as np, pandas as pd

D = "/home/user/alpha/data/round5/m02_crypto_momentum"

_cache = {}


def load():
    if not _cache:
        _cache["close"] = pd.read_parquet(f"{D}/close.parquet")
        _cache["qv"] = pd.read_parquet(f"{D}/qv.parquet")
        _cache["trades"] = pd.read_parquet(f"{D}/trades.parquet")
    return _cache["close"], _cache["qv"], _cache["trades"]


DEFAULT = dict(
    lookback=28,        # momentum lookback, days
    top_k=5,            # coins held
    n_univ=30,          # liquid universe size
    liq_win=30,         # trailing window for liquidity rank
    liq_stat="mean",    # mean | median | trades
    min_age=60,         # days listed before eligible
    btc_sma=100,        # BTC trend filter: BTC close > SMA(btc_sma); 0 = no filter
    rebal="W-SUN",      # signal day: every Sunday close (trade Monday close); "D" = daily
    delist="last",      # last | zero
    cost_mult=1.0,
    fee_bp=10.0,
    aum=0.0,            # $; >0 adds sqrt impact
    impact_y=1.0,
    mode="momentum",    # momentum | ew_univ (equal weight whole universe) | btc (BTC only)
    skip=0,             # skip most recent `skip` days in momentum
)


def run(start, end, **kw):
    p = {**DEFAULT, **kw}
    close, qv, trades = load()
    close = close.loc[: end]
    qv = qv.loc[: end]
    ret = close.pct_change(fill_method=None)
    live = close.notna()
    age = live.cumsum()
    liqsrc = trades if p["liq_stat"] == "trades" else qv
    liqsrc = liqsrc.loc[: end]
    if p["liq_stat"] == "median":
        liq = liqsrc.rolling(p["liq_win"], min_periods=p["liq_win"] // 2).median()
    else:
        liq = liqsrc.rolling(p["liq_win"], min_periods=p["liq_win"] // 2).mean()
    adv = qv.rolling(30, min_periods=10).mean()
    vol = ret.rolling(60, min_periods=20).std()
    mom = close.shift(p["skip"]) / close.shift(p["skip"] + p["lookback"]) - 1
    btc = close["BTCUSDT"]
    trend = btc > btc.rolling(p["btc_sma"]).mean() if p["btc_sma"] else pd.Series(True, index=btc.index)

    dates = close.loc[start:end].index
    if p["rebal"] == "D":
        sig_days = set(dates)
    else:
        sig_days = set(pd.date_range(dates[0] - pd.Timedelta(days=7), dates[-1], freq=p["rebal"]))
    # signal on day t -> executes at close of t+1
    exec_target = {}
    all_idx = close.index
    pos_of = {d: i for i, d in enumerate(all_idx)}
    for t in sorted(sig_days):
        if t not in pos_of or pos_of[t] + 1 >= len(all_idx):
            continue
        te = all_idx[pos_of[t] + 1]
        if te < dates[0] - pd.Timedelta(days=1) or te > dates[-1]:
            continue
        exec_target[te] = target_weights(t, p, live, age, liq, mom, trend)

    cost_bp = lambda a: np.clip(3 + 30 / np.sqrt(np.maximum(a, 1) / 1e6), 3, 150)

    h = pd.Series(dtype=float)  # $ holdings per instrument (start equity 1)
    cash = 1.0
    eq, turn_log, n_trades, delist_events = [], [], 0, []
    prev = None
    # start: execution at first close; equity measured from close of dates[0]
    for d in dates:
        if prev is not None and len(h):
            r = ret.loc[d, h.index]
            dead = r.isna() & ~live.loc[d, h.index]
            if dead.any():
                for s in h.index[dead]:
                    if p["delist"] == "last":
                        c = (p["fee_bp"] + cost_bp(adv.loc[prev, s])) * p["cost_mult"] / 1e4
                        cash += h[s] * (1 - c)
                    delist_events.append((d, s, h[s]))
                h = h[~dead]
                r = r[~dead]
            h = h * (1 + r.fillna(0))
        tot = cash + h.sum()
        if d in exec_target:
            w = exec_target[d]
            tgt = w * tot
            allk = h.index.union(tgt.index)
            cur = h.reindex(allk).fillna(0)
            new = tgt.reindex(allk).fillna(0)
            # can only trade instruments live today
            tradable = live.loc[d, allk]
            new[~tradable] = cur[~tradable]
            dv = (new - cur).abs()
            dv = dv[dv > 1e-12]
            if len(dv):
                a = adv.loc[prev if prev is not None else d, dv.index].fillna(1e6)
                c = (p["fee_bp"] + cost_bp(a)) / 1e4
                if p["aum"] > 0:
                    sig = vol.loc[d, dv.index].fillna(0.05)
                    c = c + p["impact_y"] * sig * np.sqrt(dv * p["aum"] / a.clip(lower=1))
                cost = float((dv * c).sum()) * p["cost_mult"]
                n_trades += int((dv > 1e-6 * tot).sum())
                turn_log.append(float(dv.sum()) / tot)
            else:
                cost = 0.0
            h = new[new > 1e-12]
            cash = tot - h.sum() - cost
        eq.append(cash + h.sum())
        prev = d
    eq = pd.Series(eq, index=dates)
    return eq, dict(turnover=turn_log, n_trades=n_trades, delist=delist_events,
                    targets=exec_target)


def target_weights(t, p, live, age, liq, mom, trend):
    if p["mode"] == "btc":
        return pd.Series({"BTCUSDT": 1.0}) if trend.loc[t] else pd.Series(dtype=float)
    if not trend.loc[t]:
        return pd.Series(dtype=float)
    elig = live.loc[t] & (age.loc[t] >= p["min_age"]) & liq.loc[t].notna() & mom.loc[t].notna()
    L = liq.loc[t][elig].sort_values(ascending=False).head(p["n_univ"])
    if p["mode"] == "ew_univ":
        return pd.Series(1.0 / len(L), index=L.index)
    m = mom.loc[t, L.index].sort_values(ascending=False)
    top = m.head(p["top_k"]).index
    return pd.Series(1.0 / len(top), index=top)


def stats(eq, start=None):
    eq = eq.dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan
    return dict(cagr=cagr, maxdd=dd, sharpe=sharpe, years=yrs)


def bench_btc(start, end):
    close, _, _ = load()
    return close.loc[start:end, "BTCUSDT"].dropna()


def bench_spy(start, end):
    s = pd.read_csv(f"{D}/spy.csv", index_col=0, parse_dates=True).squeeze()
    s = s.loc[start:end]
    return s
