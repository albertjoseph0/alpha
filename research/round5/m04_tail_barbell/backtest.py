"""m04 tail barbell: daily mark-to-model backtest engine.

Strategy (one configuration = depth, tenor, budget, monetize, cost case):
  * Equity sleeve: SPY total return (SPY adj close from 1993-01-29; before that ^SP500TR minus 9.45 bp/yr).
  * Put sleeve: on the first trading day of every month (the "roll", calendar-based, no signal) sell
    the whole existing put tranche at the model bid and buy a new tranche of SPX puts:
        strike K = S_t * (1 - depth), rounded to a multiple of 5 index points,
        expiry = 3rd Friday of calendar month (m + tenor)  (tenor 2 -> about 75-80 days at purchase),
        premium spent (at the ask) = budget / 12 * NAV_t.
    Everything else (all sale proceeds, all crash gains) sits in the equity sleeve. So the portfolio is
    about (1 - put mark) equity and the puts, with no T-bill sleeve: Universa-style "small premium,
    huge convexity" barbell. The annual gross premium outlay is `budget` (Spitznagel's 3.33%/yr bleed
    corresponds to budget=0.033 with the tranche expiring worthless).
  * Monetize rule: "none" = crash gains are realised at the next monthly roll only. "Mx" = if the
    tranche's model mark at the close of t-1 is >= M x its purchase cost, sell at the close of t
    (1-day lag), put the proceeds in equity and immediately re-strike a fresh tranche
    (K = S_t (1-depth), same tenor rule, premium = budget/12 * NAV_t).
  * Pricing: model mid from the daily VIX/VIX3M/VIX6M/VIX1Y/SKEW-calibrated surface (base "linz"
    model, or SSVI for the expensive case). Trades at mid +/- half-spread, half-spread = max(hpct*mid,
    floor) where hpct = 2.5% (base) or 5% (2x), floor = 0 (base) or 0.05 index points ("tick" case).
    Equity sleeve flows cost 1 bp. Marks for NAV are model mids (no spread).
  * The option is European, AM settlement is ignored (never held to expiry: always sold at the next
    roll with at least ~6 weeks left).
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from pricing import linz_put, put_price, varswap_total_var  # noqa: E402

D = Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell"
TENORS_D = np.array([2, 7, 14, 21, 30, 45, 60, 75, 91, 120, 150, 182, 213])
EQ_COST = 0.0001


def load():
    p = pd.read_pickle(D / "panel.pkl")
    s = pd.read_pickle(D / "surface.pkl")
    df = p[["SPX", "r", "q", "r_eq", "r_bill", "VIX", "SKEW"]].join(
        s[["beta", "sa30", "VIX3M_used", "VIX6M_used", "VIX1Y_used"] + [f"sa_{t}" for t in TENORS_D]])
    ss = D / "surface_ssvi.pkl"
    if ss.exists():
        df = df.join(pd.read_pickle(ss)[["psi", "ratio"]])
    df["r_eq"] = df["r_eq"].fillna(0.0)
    df["r_bill"] = df["r_bill"].fillna(0.0)
    return df


def third_friday(y, m):
    d = pd.Timestamp(y, m, 1)
    off = (4 - d.weekday()) % 7
    return d + pd.Timedelta(days=off + 14)


def expiry_for(dt, tenor_m):
    m = dt.month - 1 + tenor_m
    return third_friday(dt.year + m // 12, m % 12 + 1)


class Pricer:
    def __init__(self, df, model):
        self.model = model
        self.S = df.SPX.values
        self.r = df.r.values
        self.q = df.q.values
        self.beta = df.beta.values
        self.saw = np.stack([df[f"sa_{t}"].values ** 2 * t / 365 for t in TENORS_D], 1)  # total var
        self.Tg = TENORS_D / 365
        if model == "ssvi":
            self.psi = df.psi.values
            self.ratio = df.ratio.values
            self.v = np.stack([df.VIX.values, df.VIX3M_used.values, df.VIX6M_used.values,
                               df.VIX1Y_used.values], 1) / 100

    def put(self, i, K, tau):
        S = self.S[i]
        if tau <= 1e-6:
            return max(K - S, 0.0)
        if self.model == "linz":
            Tg = self.Tg
            if tau <= Tg[0]:
                w = self.saw[i, 0] * tau / Tg[0]
            elif tau >= Tg[-1]:
                w = self.saw[i, -1] * tau / Tg[-1]
            else:
                w = float(np.interp(tau, Tg, self.saw[i]))
            sa = math.sqrt(w / tau)
            return linz_put(S, K, tau, self.r[i], self.q[i], sa, self.beta[i])
        th = self.ratio[i] * varswap_total_var(tau, *self.v[i])
        return put_price(S, K, tau, self.r[i], self.q[i], th, self.psi[i], -0.7)


def run(df, pr, depth, tenor, budget, monet, hpct, floor=0.0, keep_daily=False):
    idx = df.index
    S = df.SPX.values
    r_eq = df.r_eq.values
    month = idx.month.values
    n = len(idx)
    eq, n_c, K, exp, cost = 1.0, 0.0, 0.0, None, 0.0
    nav = np.empty(n)
    putv = np.empty(n)
    last_mark = 0.0
    trades = []
    prem_paid = 0.0
    sale_proc = 0.0

    def half(mid):
        return max(hpct * mid, floor)

    def buy(i, navi):
        nonlocal eq, n_c, K, exp, cost, prem_paid
        K = 5.0 * round(S[i] * (1 - depth) / 5.0)
        exp = expiry_for(idx[i], tenor)
        tau = (exp - idx[i]).days / 365
        mid = pr.put(i, K, tau)
        ask = mid + half(mid)
        spend = budget / 12 * navi
        n_c = spend / ask
        cost = spend
        eq -= spend * (1 + EQ_COST)
        prem_paid += spend
        return mid

    def sell(i):
        nonlocal eq, n_c, sale_proc
        tau = (exp - idx[i]).days / 365
        mid = pr.put(i, K, tau)
        bid = max(mid - half(mid), 0.0)
        proceeds = n_c * bid
        eq += proceeds * (1 - EQ_COST)
        sale_proc += proceeds
        n_c = 0.0
        return proceeds

    for i in range(n):
        if i > 0:
            eq *= 1 + r_eq[i]
        mark = n_c * pr.put(i, K, (exp - idx[i]).days / 365) if n_c > 0 else 0.0
        navi = eq + mark
        roll = i == 0 or month[i] != month[i - 1]
        trig = monet is not None and n_c > 0 and last_mark >= monet * cost and not roll
        if roll or trig:
            proceeds = sell(i) if n_c > 0 else 0.0
            if proceeds or roll:
                trades.append((idx[i], "monetize" if trig else "roll", proceeds, cost))
            navi = eq
            m = buy(i, navi)
            mark = n_c * m
            navi = eq + mark
        nav[i] = navi
        putv[i] = mark
        last_mark = mark
    out = pd.DataFrame({"nav": nav, "put_w": putv / nav}, index=idx)
    stats = dict(prem_paid=prem_paid, sale_proc=sale_proc,
                 n_monetize=sum(1 for t in trades if t[1] == "monetize"), n_rolls=sum(1 for t in trades if t[1] == "roll"))
    return out, stats, trades


def bench(df, kind, cash=0.03, dd_trig=0.20):
    """Comparators. spy: 100% equity sleeve. 97_3: 97% equity / 3% T-bills rebalanced monthly.
    cashcrash: 97/3 rebalanced monthly while armed; when SPX closes >= dd_trig below its 252-day high
    (signal at t-1, trade at t), all cash goes into equity; cash is rebuilt to 3% on the first close at a
    new 252-day high (signal t-1), then monthly 97/3 rebalancing resumes."""
    r_eq, r_b = df.r_eq.values, df.r_bill.values
    month = df.index.month.values
    S = df.SPX.values
    hi = pd.Series(S).rolling(252, min_periods=1).max().values
    n = len(df)
    nav = np.empty(n)
    if kind == "spy":
        nav = np.cumprod(1 + np.r_[0.0, r_eq[1:]])
        return pd.DataFrame({"nav": nav}, index=df.index), {}
    eq, c = 1 - cash, cash
    armed = True
    n_dep = 0
    for i in range(n):
        if i > 0:
            eq *= 1 + r_eq[i]
            c *= 1 + r_b[i]
        tot = eq + c
        if kind == "cashcrash" and i > 0:
            dd_prev = S[i - 1] / hi[i - 1] - 1
            if armed and dd_prev <= -dd_trig:
                eq += c * (1 - EQ_COST); c = 0.0; armed = False; n_dep += 1
            elif not armed and S[i - 1] >= hi[i - 1]:
                armed = True
                tgt = cash * tot
                eq -= tgt; c = tgt
        if armed and (i == 0 or month[i] != month[i - 1]):
            tgt = cash * tot
            eq -= (tgt - c) * (1 + EQ_COST * np.sign(tgt - c)); c = tgt
        nav[i] = eq + c
    return pd.DataFrame({"nav": nav}, index=df.index), {"n_deploy": n_dep}


def metrics(nav, ref=None):
    r = nav.pct_change().dropna()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    dd = (nav / nav.cummax() - 1).min()
    vol = r.std() * math.sqrt(252)
    out = dict(cagr=cagr, vol=vol, maxdd=dd, sharpe_raw=r.mean() * 252 / vol if vol > 0 else np.nan)
    if ref is not None:
        rr = ref.pct_change().dropna()
        cr = (ref.iloc[-1] / ref.iloc[0]) ** (1 / yrs) - 1
        out["excess_vs_ref"] = cagr - cr
    return out


def yearly(nav):
    y = nav.resample("YE").last()
    first = nav.iloc[0]
    return y.pct_change().fillna(y.iloc[0] / first - 1)


def cagr_excl(nav, years):
    """CAGR after removing the calendar-year returns of `years` (chain-linking the rest)."""
    yr = yearly(nav)
    keep = yr[~yr.index.year.isin(years)]
    frac = (nav.index[-1] - nav.index[0]).days / 365.25 - sum(
        ((nav[nav.index.year == y].index[-1] - nav[nav.index.year == y].index[0]).days + 1) / 365.25
        for y in years if (nav.index.year == y).any())
    return float(np.prod(1 + keep.values) ** (1 / frac) - 1)
