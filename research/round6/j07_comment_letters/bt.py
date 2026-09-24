"""Monthly long-only portfolio simulator with explicit turnover costs, and the overlay rules.

Month m (month-end ME): universe = PIT S&P 500 members at ME with a price at t0; information = events disseminated
on or before ME; trade at the close of the first trading day after ME (t0); hold to t1 (next month's t0).
Cost = c_per_side * sum|w_target - w_drifted| (buys + sells), charged at each rebalance."""
from common import *

R = pd.read_parquet(DATA / "member_ret.parquet")
M = pd.read_csv(DATA / "months.csv", parse_dates=["month_end", "t0", "t1"])
CL = pd.read_parquet(DATA / "close.parquet")
SPY = R.groupby("month_end").spy.first()


def momentum_table():
    """12-1 momentum at each ME from closes on or before ME (skip the most recent month)."""
    cal = CL["SPY"].dropna().index
    C = CL.loc[cal].ffill(limit=5)
    out = {}
    for me in M.month_end:
        i = cal.searchsorted(me, side="right") - 1
        if i - 252 < 0:
            continue
        out[me] = C.iloc[i - 21] / C.iloc[i - 252] - 1
    return pd.DataFrame(out).T  # index month_end, columns tickers


def exclusion_sets(ev: pd.DataFrame, flag_col: str, window_days: int = 365) -> dict:
    """ME -> set of tickers with a flagged event disseminated in (ME - window, ME]."""
    f = ev[ev[flag_col] == 1][["ticker", "dissem"]]
    out = {}
    for me in M.month_end:
        s = f[(f.dissem <= me) & (f.dissem > me - pd.Timedelta(days=window_days))]
        out[me] = set(s.ticker)
    return out


def simulate(holdings: dict, months, costs=(0.0005, 0.001, 0.002)) -> dict:
    """holdings: ME -> list of tickers (equal weight). Returns dict with monthly series per cost level."""
    months = [m for m in months if m in holdings]
    gross, turn, nh = [], [], []
    prev_w = pd.Series(dtype=float)
    for me in months:
        r = R[R.month_end == me].set_index("ticker").ret
        h = [t for t in holdings[me] if t in r.index and not np.isnan(r[t])]
        if not h:
            gross.append(0.0); turn.append(prev_w.abs().sum()); nh.append(0); prev_w = pd.Series(dtype=float); continue
        w = pd.Series(1.0 / len(h), index=h)
        idx = w.index.union(prev_w.index)
        turn.append((w.reindex(idx, fill_value=0) - prev_w.reindex(idx, fill_value=0)).abs().sum())
        rr = r[h]
        g = float((w * rr).sum())
        gross.append(g)
        nh.append(len(h))
        prev_w = w * (1 + rr) / (1 + g)
    out = {"gross": pd.Series(gross, index=months), "turnover": pd.Series(turn, index=months),
           "n": pd.Series(nh, index=months)}
    for c in costs:
        out[f"net_{int(c * 1e4)}bp"] = out["gross"] - c * out["turnover"]
    return out


def stats(r: pd.Series, bench: pd.Series = None) -> dict:
    r = r.dropna()
    d = {"CAGR": cagr_m(r), "vol": r.std() * np.sqrt(12), "maxDD": maxdd(r)}
    d["Sharpe0"] = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan
    if bench is not None:
        b = bench.reindex(r.index)
        diff = r - b
        d["CAGR_bench"] = cagr_m(b)
        d["vs_bench_pts"] = (d["CAGR"] - d["CAGR_bench"]) * 100
        d["diff_t"] = diff.mean() / diff.std() * np.sqrt(len(diff)) if diff.std() > 0 else np.nan
    spy = SPY.reindex(r.index)
    d["vs_SPY_pts"] = (d["CAGR"] - cagr_m(spy)) * 100
    return d


def member_sets():
    return {me: list(g.ticker) for me, g in R[R.ret.notna()].groupby("month_end")}
