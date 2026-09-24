"""Monthly long-only portfolio from event scores.
At each month's last trading day t, every point-in-time S&P 500 member is scored by its latest filing that was
entered by t (entry = trading day after acceptance) and is at most 125 days old. Trade at the close of t+1 (next
trading day), hold to the next rebalance. Rules: 'top' = equal weight top 30% by score; 'excl' = all but the bottom
30%. Benchmarks: SPY and the equal-weight eligible universe (same timing, same costs).
Costs: COST bp per side on one-way turnover (sum |dw|), also 2x.
Survivorship bound: members without any price data can't be scored; assume they'd be held at the base rate and
return BOUND (-100% or -50%) in their last membership month, the universe mean otherwise.
usage: python s08_backtest.py <preds file> <col> <start YYYY-MM> <end YYYY-MM> [cost_bp=10] [frac=0.3]"""
import sys
from common import *


def run(preds, col, start, end, cost_bp=10.0, frac=0.3, verbose=True):
    C = pd.read_pickle(M11 / "close.pkl").astype("float64").loc["2013-01-01":]
    dates = C.index
    M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
    M["base"] = M.ticker.str.split("#").str[0]
    last_me = M.groupby("base").month_end.max()
    P = preds.dropna(subset=[col]).copy()
    P["entry_date"] = pd.to_datetime(P.entry_date)
    P = P.sort_values("entry_date")
    mes = pd.date_range(pd.Period(start).to_timestamp() - pd.Timedelta(days=1), pd.Period(end).to_timestamp("M"), freq="ME")
    # rebalance t = last trading day <= month end; exec = next trading day
    rb = [(me, dates[dates.searchsorted(me, side="right") - 1]) for me in mes]
    spy = C["SPY"]
    res, prev_w = [], {}
    for k in range(len(rb) - 1):
        me, t = rb[k]
        ti = dates.get_loc(t)
        ex, ex2 = dates[ti + 1], dates[dates.get_loc(rb[k + 1][1]) + 1] if dates.get_loc(rb[k + 1][1]) + 1 < len(dates) else None
        if ex2 is None:
            break
        mem = set(M.loc[M.month_end == me, "base"])
        ev = P[(P.entry_date <= t) & (P.entry_date > t - pd.Timedelta(days=125)) & P.ticker.isin(mem)]
        ev = ev.groupby("ticker").tail(1).set_index("ticker")
        cols_ok = [c for c in ev.index if c in C.columns and np.isfinite(C.at[ex, c])]
        ev = ev.loc[cols_ok]
        miss = [m for m in mem if m not in C.columns or not np.isfinite(C.at[ex, m] if m in C.columns else np.nan)]
        n_exit_miss = sum(1 for m in miss if last_me.get(m, me) <= me + pd.offsets.MonthEnd(1))
        # stock returns ex -> ex2 (delisted inside: last available price, then cash)
        def pret(tk):
            seg = C.loc[ex:ex2, tk].values
            ok = np.where(np.isfinite(seg))[0]
            return seg[ok[-1]] / seg[0] - 1
        allr = pd.Series({tk: pret(tk) for tk in ev.index})
        sc = ev[col]
        n = len(sc)
        port = {}
        port["univ"] = list(sc.index)
        port["top"] = list(sc.sort_values(ascending=False).index[: max(int(round(frac * n)), 1)])
        port["excl"] = list(sc.sort_values(ascending=False).index[: n - int(round(frac * n))])
        row = {"me": me, "exec": ex, "n_elig": n, "n_members": len(mem), "n_miss": len(miss),
               "n_exit_miss": n_exit_miss, "spy": spy[ex2] / spy[ex] - 1}
        for nm, names in port.items():
            w = pd.Series(1.0 / len(names), index=names)
            r = allr[names]
            rp = float((w * r).sum())
            old = prev_w.get(nm, pd.Series(dtype=float))
            turn = float(w.sub(old, fill_value=0).abs().sum()) if len(old) else 1.0
            # drifted weights for next month's turnover
            wd = w * (1 + r)
            prev_w[nm] = wd / wd.sum()
            row[f"{nm}_gross"] = rp
            row[f"{nm}_turn"] = turn
        res.append(row)
    R = pd.DataFrame(res).set_index("me")
    for nm in ("univ", "top", "excl"):
        for mult in (1, 2):
            R[f"{nm}_net{mult}"] = R[f"{nm}_gross"] - R[f"{nm}_turn"] * cost_bp * mult / 1e4
        for b in (-1.0, -0.5):
            f = R.n_miss / R.n_members
            rmiss = (R.n_exit_miss * b + (R.n_miss - R.n_exit_miss) * R.univ_gross) / R.n_miss.replace(0, 1)
            R[f"{nm}_net1_b{int(-b*100)}"] = (1 - f) * R[f"{nm}_net1"] + f * rmiss
    return R


def summary(R, label=""):
    yrs = len(R) / 12
    def cg(x):
        return (1 + x).prod() ** (1 / yrs) - 1
    def mdd(x):
        eq = (1 + x).cumprod(); return (eq / eq.cummax() - 1).min()
    s = {"months": len(R), "SPY": cg(R.spy)}
    for nm in ("univ", "top", "excl"):
        s[f"{nm}_net"] = cg(R[f"{nm}_net1"])
        s[f"{nm}_net2x"] = cg(R[f"{nm}_net2"])
        s[f"{nm}_b100"] = cg(R[f"{nm}_net1_b100"])
        s[f"{nm}_b50"] = cg(R[f"{nm}_net1_b50"])
        s[f"{nm}_mdd"] = mdd(R[f"{nm}_net1"])
        s[f"{nm}_turn"] = R[f"{nm}_turn"].iloc[1:].mean()
    s["SPY_mdd"] = mdd(R.spy)
    s["top_minus_univ_net"] = s["top_net"] - s["univ_net"]
    ex = R.top_net1 - R.univ_net1
    s["top_vs_univ_t"] = ex.mean() / ex.std() * np.sqrt(len(ex))
    return pd.Series(s, name=label)


if __name__ == "__main__":
    f, col, a, b = sys.argv[1:5]
    cost = float(sys.argv[5]) if len(sys.argv) > 5 else 10.0
    frac = float(sys.argv[6]) if len(sys.argv) > 6 else 0.3
    R = run(pd.read_parquet(DATA / f), col, a, b, cost, frac)
    print(summary(R, col).to_string())
