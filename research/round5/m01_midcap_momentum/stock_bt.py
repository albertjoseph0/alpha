"""Stock-level S&P 400 12-1 momentum backtest (point-in-time membership from Wikipedia changes,
prices from yfinance) with explicit survivorship bounds and an optional trend switch.

Timing (1-day lag): rank at the close of the LAST trading day of month m using prices up to that
close; trade at the close of the FIRST trading day of month m+1; hold to the next trade date.

Missing members (reconstructed members with no usable yfinance history at formation) are the
survivorship hole. Scenarios:
  'drop'    : ignore them (survivor-biased; what a naive yfinance backtest does)
  'neutral' : each missing member is selected with the same chance as a random member
              (expected slots = N * n_missing / n_members), and earns the equal-weight universe return
  'm50'     : same selection rate, each such slot earns -50% over the holding month
  'm100'    : same, -100%
"""
from common import *

C = pd.read_pickle(DATA / "close.pkl")
V = pd.read_pickle(DATA / "volume.pkl")
M = pd.read_csv(DATA / "membership_monthly.csv", parse_dates=["month_end"])
spy = C["SPY"].dropna()
cal = spy.index
C = C.reindex(cal)
V = V.reindex(cal)

# month-end formation days and next-day trade days
ym = cal.to_period("M")
last_idx = pd.Series(np.arange(len(cal)), index=cal).groupby(ym).max().values
FORM = cal[last_idx]
TRADE = cal[np.minimum(last_idx + 1, len(cal) - 1)]
MEMBERS = {me.to_period("M"): set(g.ticker) for me, g in M.groupby("month_end")}


def momentum_at(i):
    """12-1 momentum at calendar index i, with data-quality mask."""
    p0, p1 = C.iloc[i - 252], C.iloc[i - 21]
    win = C.iloc[i - 252:i + 1]
    ok = (win.notna().sum() >= 245) & C.iloc[i].notna() & p0.notna() & p1.notna()
    return (p1 / p0 - 1).where(ok)


def build_book(N=10, scen="drop", start="2012-01", end="2026-08", min_members=300):
    """Returns DataFrame per holding month: gross return, turnover, holdings, n_missing..."""
    rows = []
    prev_w = pd.Series(dtype=float)
    for k in range(len(FORM) - 1):
        f, t0, t1 = FORM[k], TRADE[k], TRADE[k + 1]
        per = f.to_period("M")
        if per < pd.Period(start) - 1 or per > pd.Period(end) - 1:
            continue
        mem = MEMBERS.get(per)
        if mem is None or len(mem) < min_members:
            continue
        i = cal.get_loc(f)
        mom = momentum_at(i)
        have = [m for m in mem if m in mom.index and pd.notna(mom.get(m))]
        n_mem, n_miss = len(mem), len(mem) - len(have)
        s = mom[have].sort_values(ascending=False)
        top = list(s.index[:N])
        # holding-period return per name (entry close t0 -> exit close t1); if the price
        # series ends inside the window, exit at the last available price (then cash)
        pe = C.loc[t0, have]
        win = C.loc[t0:t1, have]
        px = win.ffill().iloc[-1]
        hr = (px / pe - 1)
        uni = hr.mean()                     # equal-weight universe (survivors) return
        rtop = hr[top]
        # drifted weights at exit for turnover next month
        miss_slots = N * n_miss / n_mem if scen != "drop" else 0.0
        w_real = (N - miss_slots) / N
        r_miss = {"drop": 0.0, "neutral": uni, "m50": -0.5, "m100": -1.0}[scen]
        gross = w_real * rtop.mean() + (1 - w_real) * r_miss
        # turnover vs previous drifted book (phantom slots assumed fully replaced each month)
        w_new = pd.Series(w_real / N, index=top)
        allk = w_new.index.union(prev_w.index)
        to = (w_new.reindex(allk, fill_value=0) - prev_w.reindex(allk, fill_value=0)).abs().sum()
        to += 2 * (1 - w_real)
        drift = (w_new * (1 + rtop))
        prev_w = drift / drift.sum() * w_real if drift.sum() > 0 else w_new
        # liquidity: min 63-day median dollar volume among holdings at formation
        dv = (C.iloc[i - 62:i + 1][top] * V.iloc[i - 62:i + 1][top]).median()
        rows.append(dict(form=f, t0=t0, t1=t1, gross=gross, uni=uni, to=to, n_mem=n_mem,
                         n_miss=n_miss, hold=",".join(top), min_dv=dv.min(), med_dv=dv.median(),
                         top_mom=s.iloc[:N].mean(), top_ret_max=rtop.max(), top_ret_min=rtop.min()))
    return pd.DataFrame(rows).set_index("t1")


def spy_period(book):
    return pd.Series([C.loc[b.t1, "SPY"] / C.loc[b.t0, "SPY"] - 1 for _, b in book.iterrows()], index=book.index)


def period_regime(book, trend_series=None):
    """Trend ensemble on SPY (126/168/210/252-day), read at the close of the formation day
    (= one day before the trade), so the switch uses the same 1-day lag."""
    s = C["SPY"] if trend_series is None else trend_series
    lp = np.log(s)
    up = sum(((lp - lp.shift(L)) > 0).astype(float) for L in TREND_LENGTHS) / len(TREND_LENGTHS)
    return up.reindex(book["form"].values).set_axis(book.index)


def defense_period(book, cost_mult=1.0):
    d = defense_sleeve_daily(cost_mult)
    eq = (1 + d).cumprod()
    return pd.Series([eq.loc[:b.t1].iloc[-1] / eq.loc[:b.t0].iloc[-1] - 1 for _, b in book.iterrows()],
                     index=book.index)


def net(book, c_oneway, switch=False, cost_mult_def=1.0, c_def=0.0003):
    r = book["gross"] - book["to"] * c_oneway
    if not switch:
        return r
    u = period_regime(book)
    dfn = defense_period(book, cost_mult_def)
    du = u.diff().abs().fillna(0)
    return u * r + (1 - u) * dfn - du * (c_oneway + c_def)


def yearly(r):
    return (1 + r).groupby(r.index.year).prod() - 1


def ann(r, n_years):
    return (1 + r).prod() ** (1 / n_years) - 1


def summary(r, bench, label):
    yrs = (r.index[-1] - r.index[0]).days / 365.25 + 1 / 12
    cr, cb = ann(r, yrs), ann(bench, yrs)
    ey = yearly(r) - yearly(bench)
    return dict(label=label, cagr=cr, spy=cb, excess=cr - cb, maxdd=maxdd(r), vol=r.std() * np.sqrt(12),
                yrs_beat=f"{(ey > 0).sum()}/{len(ey)}", months=len(r))
