"""Shared analysis functions: costs, bet selection, per-bet metrics, calendar-time portfolio simulation.

Cost model (cost multiplier k: 1 = base, 2 = "2x costs"):
  Kalshi   : exec = ask + 0.5c*k (+ (ask-mid)*(k-1): the half-spread is paid again at 2x)
             fee/contract = ceil_to_cent(0.07 * C * exec*(1-exec)) / C * k, C = order size (default 100 contracts)
             (Kalshi general taker fee, 2026 schedule; applied to all periods; INX/NASDAQ100 series actually pay half)
  Polymarket: exec = hourly price (mid/last) + 1c*k ; fee/contract = 0.05*k*exec*(1-exec)
             (2026 category taker schedule 0.04-0.07; Polymarket charged 0 before 2025, so this is conservative)
Settlement: winner pays $1 (Polymarket: final outcomePrices; 0.5/0.5 = void refund at 0.5).
"""
import numpy as np
import pandas as pd

SPY_FILE = "data/etf_daily.csv"


def exec_and_fee(df, k=1.0, C=100):
    p = df.p.values
    if df.venue.iloc[0] == "kalshi":
        half = np.nan_to_num(p - df.pmid.values, nan=0.005)
        ex = p + 0.005 * k + half * (k - 1)
        fee = np.ceil(np.round(0.07 * C * ex * (1 - ex) * 100, 6)) / 100 / C * k
    else:
        ex = p + 0.01 * k
        fee = 0.05 * k * ex * (1 - ex)
    return ex, fee


def select(snap, H, lo, hi, k=1.0, C=100, max_age=24.0, filters=None):
    """bets = snapshots at horizon H whose tradeable price (before slippage) is in [lo, hi]."""
    s = snap[(snap.H == H) & snap.p.between(lo, hi) & snap.pay.notna() & (snap.age_h <= max_age)]
    for f in (filters or []):
        s = s[s[f]]
    if s.empty:
        return s
    s = s.copy()
    s["ex"], s["fee"] = exec_and_fee(s, k, C)
    s["cost"] = s.ex + s.fee
    s["pnl"] = s.pay - s.cost                 # per contract
    s["ret"] = s.pnl / s.cost                  # per $ staked
    s["days"] = np.maximum((s.settle_ts - s.d) / 86400.0, 1 / 24)
    # equal split of one unit of event capital over its qualifying markets (correlated strikes)
    s["w"] = 1.0 / s.groupby("event").mkt.transform("size")
    return s


def event_bets(s):
    """collapse market bets to event bets (weighted by w)."""
    s = s.assign(cap=s["cap"] if "cap" in s else np.inf)
    g = s.assign(wr=s.w * s.ret, wd=s.w * s.days, wp=s.w * s.p, wpay=s.w * s.pay, wpnl=s.w * s.pnl,
                 won=(s.pay >= 0.999) * s.w)
    e = g.groupby("event").agg(d=("d", "min"), settle_ts=("settle_ts", "max"), ret=("wr", "sum"), days=("wd", "sum"),
                               p=("wp", "sum"), pay=("wpay", "sum"), pnl=("wpnl", "sum"), won=("won", "sum"),
                               n=("mkt", "size"), category=("category", "first"), cap=("cap", "sum"))
    return e.reset_index()


def boot_ci(x, n=2000, seed=0, stat=np.mean):
    x = np.asarray(x)
    if len(x) < 5:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    bs = [stat(x[rng.integers(0, len(x), len(x))]) for _ in range(n)]
    return tuple(np.percentile(bs, [2.5, 97.5]))


def deployed_rate(e):
    """return per $-day of locked capital x 365 (simple, no compounding): the annual return an investor would
    earn if capital could be kept 100% deployed in bets like these (an upper bound; opportunity supply and
    capacity are the binding limits, see simulate/capacity)."""
    return 365 * e.ret.sum() / e.days.sum()


def simulate(e, f=0.05, start=None, end=None, K=None):
    """Calendar-time portfolio: stake f*equity (at decision time, capped by free cash) per event bet;
    capital locked until settlement.  Equity marked at cost while open (conservative for drawdown of losses
    realized only at settlement).  Returns dict with CAGR, maxDD, utilization, worst losing streak."""
    e = e.sort_values("d")
    t0 = start if start is not None else e.d.min()
    t1 = end if end is not None else e.settle_ts.max()
    cash, open_ = (1.0 if K is None else float(K)), []           # open: (settle_ts, stake, ret)
    caps = e.cap.values if (K is not None and "cap" in e) else np.full(len(e), np.inf)
    eq_path, util, locked_days = [], [], 0.0
    evs = list(zip(e.d.values, e.settle_ts.values, e.ret.values, caps))
    import heapq
    heap = []
    for d, st, r, cp in evs:
        while heap and heap[0][0] <= d:
            st0, stake0, r0 = heapq.heappop(heap)
            cash += stake0 * (1 + r0)
            eq_path.append((st0, cash + sum(h[1] for h in heap)))
        equity = cash + sum(h[1] for h in heap)
        stake = min(f * equity, cash, cp)
        if stake <= 0:
            continue
        cash -= stake
        locked_days += stake / equity * (st - d) / 86400
        heapq.heappush(heap, (st, stake, r))
    while heap:
        st0, stake0, r0 = heapq.heappop(heap)
        cash += stake0 * (1 + r0)
        eq_path.append((st0, cash + sum(h[1] for h in heap)))
    path = pd.Series([v for _, v in eq_path], index=pd.to_datetime([t for t, _ in eq_path], unit="s"))
    yrs = (t1 - t0) / (365.25 * 86400)
    k0 = 1.0 if K is None else float(K)
    cagr = (path.iloc[-1] / k0) ** (1 / yrs) - 1 if len(path) else 0.0
    dd = (path / path.cummax() - 1).min() if len(path) else 0.0
    # worst losing streak in settlement order (event bets with pnl < 0)
    loss = (e.sort_values("settle_ts").pnl < 0).values
    streak = best = 0
    for x in loss:
        streak = streak + 1 if x else 0
        best = max(best, streak)
    worst_bet = e.ret.min()
    return dict(final=float(path.iloc[-1]) / k0 if len(path) else 1.0, cagr=float(cagr), maxdd=float(dd), years=yrs,
                util=float(locked_days / ((t1 - t0) / 86400)), streak=int(best), worst_bet=float(worst_bet))


def spy_cagr(t0, t1, root="."):
    s = pd.read_csv(f"{root}/{SPY_FILE}", usecols=["date", "SPY"], parse_dates=["date"]).dropna()
    s = s[(s.date >= pd.to_datetime(t0, unit="s")) & (s.date <= pd.to_datetime(t1, unit="s"))]
    g = (1 + s.SPY).prod()
    yrs = (t1 - t0) / (365.25 * 86400)
    return g ** (1 / yrs) - 1


def calib(snap, bins, by_event=True, seed=0):
    """realized win-rate of the leading side vs its tradeable price; CI = event-cluster bootstrap."""
    s = snap[snap.pay.notna() & snap.p.notna()].copy()
    s["bin"] = pd.cut(s.p, bins, right=True)
    rows = []
    rng = np.random.default_rng(seed)
    for b, g in s.groupby("bin", observed=True):
        win = (g.pay >= 0.999).astype(float) + 0.5 * ((g.pay > 0.001) & (g.pay < 0.999))
        ev = g.event.values
        uev, inv = np.unique(ev, return_inverse=True)
        sw = np.bincount(inv, weights=win.values)
        sn = np.bincount(inv).astype(float)
        bs = []
        for _ in range(1000):
            ix = rng.integers(0, len(uev), len(uev))
            bs.append(sw[ix].sum() / sn[ix].sum())
        lo, hi = np.percentile(bs, [2.5, 97.5])
        rows.append(dict(bin=str(b), n=len(g), events=len(uev), mean_p=g.p.mean(), win=win.mean(), lo=lo, hi=hi))
    return pd.DataFrame(rows)
