"""Stock-level S&P 400 12-1 momentum backtest (point-in-time membership, yfinance prices) with
explicit survivorship bounds and an optional SPY trend switch into the deep_trend_switch defense sleeve.

Timing (1-day lag): rank at the close of the LAST trading day of month m using prices up to that
close; trade at the close of the FIRST trading day of month m+1; hold to the next trade date.
Momentum = close[t-21] / close[t-252] - 1 (12-1), requiring >= 245 valid closes in the window.

Membership sources (all point-in-time month-end snapshots):
  'chg'  : membership_monthly.csv, current list walked backwards through Wikipedia's change table
  'rev'  : membership_wikirev.csv, the constituents table of the Wikipedia revision saved on or before
           each month end (independent, strictly PIT; editor lag only makes it stale)
  'both' : intersection of the two (names both sources agree were members)

Survivorship hole: a member with NO price at the formation close ("missing": delisted, acquired,
ticker lost). Members that have a price but < 12 months of history (recent IPOs / spin-offs) are
ineligible in live trading as well and are not part of the hole.
Scenarios for the hole (missing names assumed picked at the random rate: expected missing slots
= N * n_miss / n_mem):
  'drop'    : ignore them (survivor-biased; what a naive yfinance backtest does)
  'neutral' : missing slots earn the equal-weight eligible-universe return
  'x50'/'x100': as neutral, but missing names that LEAVE the index before the next formation earn
               -50% / -100% in that holding month (their exit is a delisting at a loss)
  'm50'/'m100': every missing slot earns -50% / -100% EVERY month (literal extreme bound)
"""
from functools import lru_cache
from common import *

C = pd.read_pickle(DATA / "close.pkl")
V = pd.read_pickle(DATA / "volume.pkl")
spy = C["SPY"].dropna()
cal = spy.index
C = C.reindex(cal)
V = V.reindex(cal)
B = pd.read_pickle(DATA / "bench_close.pkl").reindex(cal)

ym = cal.to_period("M")
last_idx = pd.Series(np.arange(len(cal)), index=cal).groupby(ym).max().values
FORM = cal[last_idx]
TRADE = cal[np.minimum(last_idx + 1, len(cal) - 1)]
_MEM = {}


def members(src="chg"):
    if src in _MEM:
        return _MEM[src]
    if src == "both":
        a, b = members("chg"), members("rev")
        out = {k: a[k] & b[k] for k in a if k in b}
    else:
        f = {"chg": "membership_monthly.csv", "rev": "membership_wikirev.csv"}[src]
        M = pd.read_csv(DATA / f, parse_dates=["month_end"])
        out = {me.to_period("M"): set(g.ticker) for me, g in M.groupby("month_end")}
    _MEM[src] = out
    return out


@lru_cache(maxsize=None)
def momentum_at(i):
    """12-1 momentum where the series is long enough; also returns a 'bad data' mask: series with a
    price and full history but >5% zero/NaN-volume days in the window (dead or re-used tickers such
    as CPWR/SUNE, whose yfinance history belongs to a different, untraded security)."""
    p0, p1 = C.iloc[i - 252], C.iloc[i - 21]
    win = C.iloc[i - 252:i + 1]
    long = (win.notna().sum() >= 245) & C.iloc[i].notna() & p0.notna() & p1.notna()
    vw = V.iloc[i - 252:i + 1]
    clean = ((vw == 0) | vw.isna()).mean() <= 0.05
    return (p1 / p0 - 1).where(long & clean), long & ~clean


def build_book(N=10, scen="drop", start="2012-01", end="2018-12", src="chg", min_members=300):
    """One row per holding month (start..end are HOLDING months, i.e. month of t0)."""
    MEM = members(src)
    rows = []
    prev_w = pd.Series(dtype=float)
    for k in range(len(FORM) - 1):
        f, t0, t1 = FORM[k], TRADE[k], TRADE[k + 1]
        per = f.to_period("M")
        if per < pd.Period(start) - 1 or per > pd.Period(end) - 1:
            continue
        mem = MEM.get(per)
        if mem is None or len(mem) < min_members:
            continue
        nxt = MEM.get(per + 1, mem)
        i = cal.get_loc(f)
        mom, bad = momentum_at(i)
        px_f = C.iloc[i]
        missing = [m for m in mem if m not in px_f.index or pd.isna(px_f.get(m)) or bad.get(m, False)]
        have = [m for m in mem if m in mom.index and pd.notna(mom.get(m))]
        n_mem, n_miss = len(mem), len(missing)
        n_mx = sum(1 for m in missing if m not in nxt)          # missing AND leaving the index
        s = mom[have].sort_values(ascending=False)
        top = list(s.index[:N])
        pe = C.loc[t0, have]
        px = C.loc[t0:t1, have].ffill().iloc[-1]                  # delisted inside window -> last price, then cash
        hr = (px / pe - 1)
        uni = hr.mean()
        rtop = hr[top].fillna(0.0)
        q = hr[list(s.index[:max(1, len(s) // 5)])].mean()         # top quintile, equal weight
        f_miss = 0.0 if scen == "drop" else n_miss / n_mem
        if scen in ("drop", "neutral"):
            r_miss = uni
        elif scen in ("x50", "x100"):
            loss = -0.5 if scen == "x50" else -1.0
            r_miss = ((n_miss - n_mx) * uni + n_mx * loss) / n_miss if n_miss else 0.0
        else:
            r_miss = -0.5 if scen == "m50" else -1.0
        w_real = 1.0 - f_miss
        gross = w_real * rtop.mean() + f_miss * r_miss
        w_new = pd.Series(w_real / N, index=top)
        allk = w_new.index.union(prev_w.index)
        to = (w_new.reindex(allk, fill_value=0) - prev_w.reindex(allk, fill_value=0)).abs().sum()
        to += 2 * f_miss                                           # phantom slots fully replaced monthly
        n_new = len(set(top) - set(prev_w.index))
        drift = w_new * (1 + rtop)
        prev_w = drift / drift.sum() * w_real if drift.sum() > 0 else w_new
        dv = (C.iloc[i - 62:i + 1][top] * V.iloc[i - 62:i + 1][top]).median()
        dmax = C.loc[t0:t1, top].pct_change().abs().max().max()     # data-error flag (daily |ret|)
        rows.append(dict(month=str(t0.to_period("M")), form=f, t0=t0, t1=t1, gross=gross, uni=uni, q5=q,
                         to=to, n_new=n_new, n_mem=n_mem, n_have=len(have), n_miss=n_miss, n_mx=n_mx,
                         hold=",".join(top), min_dv=dv.min(), med_dv=dv.median(), top_mom=s.iloc[:N].mean(),
                         top_ret_max=rtop.max(), top_ret_min=rtop.min(), max_daily=dmax,
                         spy=C.loc[t1, "SPY"] / C.loc[t0, "SPY"] - 1,
                         ijh=B.loc[t1, "IJH"] / B.loc[t0, "IJH"] - 1,
                         xmmo=B.loc[t1, "XMMO"] / B.loc[t0, "XMMO"] - 1))
    return pd.DataFrame(rows).set_index("t0")


def period_regime(book):
    """SPY trend ensemble (126/168/210/252-day) at the formation close, i.e. one day before the trade."""
    lp = np.log(C["SPY"])
    up = sum(((lp - lp.shift(L)) > 0).astype(float) for L in TREND_LENGTHS) / len(TREND_LENGTHS)
    return up.reindex(book["form"].values).set_axis(book.index)


def defense_period(book, cost_mult=1.0):
    d = defense_sleeve_daily(cost_mult)
    eq = (1 + d).cumprod()
    return pd.Series([eq.loc[:b.t1].iloc[-1] / eq.loc[:t0].iloc[-1] - 1 for t0, b in book.iterrows()],
                     index=book.index)


def net(book, c_oneway, switch=False, cost_mult_def=1.0, c_def=0.0003):
    r = book["gross"] - book["to"] * c_oneway
    if not switch:
        return r
    u = period_regime(book)
    dfn = defense_period(book, cost_mult_def)
    du = u.diff().abs().fillna(u.iloc[0])
    return u * r + (1 - u) * dfn - du * (c_oneway + c_def)


def ann(r):
    r = r.dropna()
    return (1 + r).prod() ** (12 / len(r)) - 1


def yearly(r):
    return (1 + r).groupby(r.index.year).prod() - 1


def summary(r, bench, label, **kw):
    ey = yearly(r) - yearly(bench)
    return dict(label=label, **kw, cagr=ann(r), bench=ann(bench), excess=ann(r) - ann(bench),
                maxdd=maxdd(r), vol=r.std() * np.sqrt(12), yrs_beat=f"{(ey > 0).sum()}/{len(ey)}",
                months=len(r))
