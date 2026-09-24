"""Shared helpers for o01 (activist 13D + Jev): paths, cost model, calendar-time portfolio backtest, stats.

Portfolio mechanics (one implementation used for DEV and TEST):
* Each selected event is bought at the CLOSE of its entry day (the first trading day after file_date) and
  held for H trading days (or until the price series ends), then sold at the close.
* Buy-and-hold weights (no daily rebalancing). A new position is sized at NAV / max(N_active, NMIN), funded
  from cash first and then by trimming existing positions pro rata. Exit proceeds wait in cash (0% return).
* Costs are one-way fractions charged on every buy, sell and trim, by liquidity bucket (see cost_oneway).
"""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "orch" / "o01_activist_13d"
R = ROOT / "research" / "orch" / "o01_activist_13d"
NMIN = 20          # no position larger than 1/20 of NAV at entry
DEV = ("2014-01-01", "2019-12-31")
TEST = ("2020-01-01", "2026-12-31")


def cost_oneway(adv: np.ndarray, price: np.ndarray) -> np.ndarray:
    """One-way cost (half-spread + slippage + commission) by 20-day median dollar volume, +25bp below $5."""
    adv = np.asarray(adv, float)
    c = np.select([adv >= 50e6, adv >= 10e6, adv >= 2e6, adv >= 0.5e6], [0.0005, 0.0015, 0.0030, 0.0060], 0.0100)
    return c + np.where(np.asarray(price, float) < 5, 0.0025, 0.0)


def load_close():
    c = pd.read_parquet(D / "px_close.parquet")
    c.index = pd.to_datetime(c.index)
    return c.sort_index()


def backtest(ev: pd.DataFrame, close: pd.DataFrame, H: int, start: str, end: str, cost_mult: float = 1.0,
             ret_override: dict | None = None):
    """ev: selected events with columns tk, entry_date, cost1. Returns daily NAV series (net) and info dict.
    Events whose entry_date is before `start` are included (warm-up) but performance is measured from start.
    ret_override: optional {event index: total return} to force a position's total return (survivorship bounds);
    the forced return is realised on the exit day."""
    cal = close.index[(close.index <= pd.Timestamp(end))]
    cal = cal[cal >= min(pd.Timestamp(start), ev["entry_date"].min() if len(ev) else pd.Timestamp(start))]
    pos_of = {d: i for i, d in enumerate(cal)}
    T = len(cal)
    entries: dict[int, list] = {}
    for idx, r in ev.iterrows():
        ei = pos_of.get(pd.Timestamp(r["entry_date"]))
        if ei is None:
            continue
        px = close[r["tk"]].reindex(cal).to_numpy()
        last_valid = np.where(~np.isnan(px))[0]
        if len(last_valid) == 0 or np.isnan(px[ei]):
            continue
        xi = min(ei + H, T - 1, last_valid.max())
        seg = pd.Series(px[ei:xi + 1]).ffill().to_numpy()
        dr = seg[1:] / seg[:-1] - 1.0
        if ret_override is not None and idx in ret_override:
            dr = np.zeros(len(dr))
            if len(dr):
                dr[-1] = ret_override[idx]
            else:
                continue
        entries.setdefault(ei, []).append((idx, xi, dr, float(r["cost1"]) * cost_mult))
    cash, nav = 1.0, np.empty(T)
    act: dict = {}  # idx -> [value, ei, xi, dr, cost]
    n_trades = 0
    gross_exposure = np.empty(T)
    for t in range(T):
        # 1) mark to market
        for k, p in act.items():
            p[0] *= 1.0 + p[3][t - p[1] - 1]
        # 2) exits at today's close
        for k in [k for k, p in act.items() if p[2] == t]:
            v, _, _, _, c = act.pop(k)
            cash += v * (1 - c)
        # 3) entries at today's close
        new = entries.get(t, [])
        if new:
            tot = cash + sum(p[0] for p in act.values())
            N = len(act) + len(new)
            tgt = tot / max(N, NMIN)
            need = tgt * len(new)
            sv = sum(p[0] for p in act.values())
            if need > cash and sv > 0:
                short = need - cash
                frac = min(short / sv, 1.0)
                for p in act.values():
                    trim = p[0] * frac
                    p[0] -= trim
                    cash += trim * (1 - p[4])
            spend = min(need, cash)
            each = spend / len(new)
            cash -= spend
            for idx, xi, dr, c in new:
                if xi > t:
                    act[idx] = [each * (1 - c), t, xi, dr, c]
                    n_trades += 1
                else:
                    cash += each
        nav[t] = cash + sum(p[0] for p in act.values())
        gross_exposure[t] = 1 - cash / nav[t] if nav[t] > 0 else 0
    s = pd.Series(nav, index=cal)
    m = s.index >= pd.Timestamp(start)
    s = s[m] / s[m].iloc[0]
    expo = pd.Series(gross_exposure, index=cal)[m]
    return s, {"n_positions": n_trades, "avg_exposure": float(expo.mean())}


def stats(nav: pd.Series, bench: dict[str, pd.Series] | None = None) -> dict:
    nav = nav.dropna()
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    r = nav.pct_change().dropna()
    dd = (nav / nav.cummax() - 1).min()
    out = {"cagr": cagr, "vol": r.std() * np.sqrt(252), "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
           "maxdd": dd, "years": yrs}
    for name, b in (bench or {}).items():
        b = b.reindex(nav.index).ffill()
        b = b / b.iloc[0]
        bc = b.iloc[-1] ** (1 / yrs) - 1
        out[f"{name}_cagr"] = bc
        out[f"x_{name}"] = cagr - bc
        br = b.pct_change().dropna()
        rr = r.reindex(br.index).fillna(0)
        X = np.vstack([np.ones(len(br)), br.to_numpy()]).T
        beta = np.linalg.lstsq(X, rr.to_numpy(), rcond=None)[0]
        resid = rr.to_numpy() - X @ beta
        se = resid.std(ddof=2) / np.sqrt(len(rr))
        out[f"alpha_{name}"] = beta[0] * 252
        out[f"alpha_t_{name}"] = beta[0] / se
        out[f"beta_{name}"] = beta[1]
    return out
