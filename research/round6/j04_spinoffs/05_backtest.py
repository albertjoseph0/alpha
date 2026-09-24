"""Step 5: event and calendar-time backtest of spin-off filters.
Rule: buy each qualifying spin-off at the OPEN of trading day N (0 = first regular-way day, so N full days of
forced selling have passed), hold M calendar months, exit at that day's close (or the last available close).
Portfolio: equal dollars at entry, no rebalancing afterwards (weights drift with each position's value); new
entries are funded by pro-rata trims. Idle money sits in SPY. Long-only, no leverage.
Costs (one-way, by spin-off market cap at day 0): >=$10B 5 bp, $2-10B 10 bp, $0.3-2B 25 bp, <$0.3B or unknown 60 bp;
every entry/exit is charged its own cost plus the same notional of trims/redeployment at the cost of the other holdings.
Usage: 05_backtest.py dev   (TEST: 05_backtest.py test --i-have-a-prereg)"""
import json, os, sys
import numpy as np
import pandas as pd
import yfinance as yf

D = "/home/user/alpha/data/round6/j04_spinoffs"
OUT = "/home/user/alpha/research/round6/j04_spinoffs"
P = f"{D}/prices"
RNG = np.random.default_rng(0)


def load_px(tk):
    h = pd.read_csv(f"{P}/{tk}.csv", index_col=0, parse_dates=True)
    h = h[h.Close > 0]
    return h


def bench(tk):
    f = f"{P}/_bench_{tk}.csv"
    if not os.path.exists(f):
        h = yf.Ticker(tk).history(period="max", auto_adjust=False)
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        h[["Open", "Close", "Adj Close"]].to_csv(f)
    return pd.read_csv(f, index_col=0, parse_dates=True)["Adj Close"]


def cost_bp(mcap):
    if not np.isfinite(mcap):
        return 60.0
    return 5.0 if mcap >= 10e9 else 10.0 if mcap >= 2e9 else 25.0 if mcap >= 0.3e9 else 60.0


def event_paths(ev, N, M):
    """Daily simple-return series per event over its holding window (first day = open->close)."""
    paths, info = {}, []
    for _, r in ev.iterrows():
        h = load_px(r.yf_ticker)
        if len(h) <= N + 1:
            continue
        adj = h["Adj Close"]
        aopen = h.Open * adj / h.Close
        d_in = h.index[N]
        d_end = d_in + pd.DateOffset(months=M)
        w = adj[(adj.index >= d_in) & (adj.index <= d_end)]
        if len(w) < 2:
            continue
        rets = w.pct_change()
        rets.iloc[0] = w.iloc[0] / aopen.loc[d_in] - 1
        rets = rets.clip(-0.95, 5.0)  # guard against bad ticks
        paths[r.cik] = rets
        info.append(dict(cik=r.cik, entry=d_in, exit=w.index[-1], planned_exit=d_end,
                         truncated=w.index[-1] < d_end - pd.Timedelta(days=7) and w.index[-1] < h.index[-1] + pd.Timedelta(days=1)
                         and h.index[-1] < pd.Timestamp("2026-09-01"),
                         ret=float((1 + rets).prod() - 1), cost_bp=cost_bp(r.mcap0)))
    return paths, pd.DataFrame(info)


def bhar(info, b):
    out = []
    for _, r in info.iterrows():
        s = b[(b.index >= r.entry) & (b.index <= r.exit)]
        prev = b[b.index < r.entry]
        base = prev.iloc[-1] if len(prev) else s.iloc[0]
        out.append(s.iloc[-1] / base - 1)
    return np.array(out)


def portfolio(paths, info, spy_ret, cost_mult=1.0, start=None, end=None):
    """Drifting equal-dollar-at-entry portfolio; SPY when empty. Returns daily net return series."""
    if not len(info):
        return None
    idx = spy_ret.index
    start = start or info.entry.min()
    end = end or info.exit.max()
    idx = idx[(idx >= start) & (idx <= end)]
    R = pd.DataFrame({c: paths[c] for c in info.cik}).reindex(idx)
    active = R.notna()
    V = (1 + R.fillna(0)).cumprod()
    # value since entry: divide by value the day before entry
    Vprev = V.shift(1).fillna(1.0)
    ent = info.set_index("cik").entry
    base = pd.Series({c: Vprev.loc[ent[c], c] if ent[c] in Vprev.index else 1.0 for c in R.columns})
    Vrel_prev = (Vprev / base).where(active, 0.0)  # weight driver: value at t-1 relative to entry (1 on entry day)
    wsum = Vrel_prev.sum(axis=1)
    gross = (Vrel_prev * R.fillna(0)).sum(axis=1) / wsum.replace(0, np.nan)
    gross = gross.where(wsum > 0, spy_ret.reindex(idx))
    # costs
    c = info.set_index("cik").cost_bp.reindex(R.columns) / 1e4 * cost_mult
    W = Vrel_prev.div(wsum.replace(0, np.nan), axis=0).fillna(0)
    avg_c = (W * c).sum(axis=1)
    first = active & ~active.shift(1, fill_value=False)
    # weight at exit (end of last active day) approximated by previous-day weight
    last = active & ~active.shift(-1, fill_value=False)
    Wf, Wl = W.where(first, 0.0), W.where(last, 0.0)
    tc = (Wf * c).sum(axis=1) + Wf.sum(axis=1) * avg_c + (Wl * c).sum(axis=1) + Wl.sum(axis=1) * avg_c
    net = gross - tc
    return net, (wsum > 0).mean(), active.sum(axis=1)


def cagr(r):
    r = r.dropna()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return (1 + r).prod() ** (1 / yrs) - 1 if yrs > 0 else np.nan


def maxdd(r):
    v = (1 + r.fillna(0)).cumprod()
    return float((v / v.cummax() - 1).min())


def summarize(name, ev_sel, paths, info, B, cost_mult=1.0, window=None):
    info = info[info.cik.isin(ev_sel.cik)]
    if len(info) < 3:
        return dict(filter=name, n=len(info))
    spy_ret = B["SPY"].pct_change()
    res = portfolio(paths, info, spy_ret, cost_mult, *(window or (None, None)))
    net, invested, nact = res
    idx = net.index
    out = dict(filter=name, n=len(info), cagr=cagr(net), maxdd=maxdd(net), invested=invested, avg_pos=float(nact[nact > 0].mean()))
    for b in ["SPY", "IWM", "IJH"]:
        br = B[b].pct_change().reindex(idx)
        out[f"{b}_cagr"] = cagr(br)
    out["ex_SPY"] = out["cagr"] - out["SPY_cagr"]
    out["ex_IWM"] = out["cagr"] - out["IWM_cagr"]
    ex = info.ret.values - bhar(info, B["SPY"])
    out["mean_bhar_spy"] = ex.mean()
    out["med_bhar_spy"] = np.median(ex)
    out["hit"] = (ex > 0).mean()
    bs = [RNG.choice(ex, len(ex)).mean() for _ in range(2000)]
    out["bhar_ci_lo"], out["bhar_ci_hi"] = np.percentile(bs, [2.5, 97.5])
    # without top-3 winners
    top = info.nlargest(3, "ret").cik
    info3 = info[~info.cik.isin(top)]
    net3 = portfolio(paths, info3, spy_ret, cost_mult, idx[0], idx[-1])[0]
    out["cagr_ex_top3"] = cagr(net3)
    out["ex_SPY_ex_top3"] = out["cagr_ex_top3"] - out["SPY_cagr"]
    return out


def boot_cagr(ev_sel, paths, info, B, nboot=300, cost_mult=1.0):
    info = info[info.cik.isin(ev_sel.cik)].reset_index(drop=True)
    spy_ret = B["SPY"].pct_change()
    s0, e0 = info.entry.min(), info.exit.max()
    spy_c = cagr(spy_ret[(spy_ret.index >= s0) & (spy_ret.index <= e0)])
    vals = []
    for _ in range(nboot):
        ii = RNG.choice(len(info), len(info))
        bi = info.iloc[ii].copy()
        bi["cik"] = [f"{c}_{k}" for k, c in enumerate(bi.cik)]
        bp = {f"{c}_{k}": paths[c] for k, c in enumerate(info.iloc[ii].cik)}
        net = portfolio(bp, bi, spy_ret, cost_mult, s0, e0)[0]
        vals.append(cagr(net) - spy_c)
    return np.percentile(vals, [2.5, 50, 97.5])
