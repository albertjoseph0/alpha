"""Calendar-time long-only event portfolio. K slots of 1/K equity each; a selected event takes a free slot at its
entry open (ties broken by score) and is held for H trading days (open to open); free slots sit in SPY.
Costs: `cost_bps` per side on every stock entry and exit, plus 1bp per side on SPY sleeve changes."""
import numpy as np, pandas as pd
from common import M06

_px = None


def prices():
    global _px
    if _px is None:
        px = pd.read_parquet(M06 / "prices.parquet")
        O = px.pivot(index="date", columns="ticker", values="Open")
        RO = (O.shift(-1) / O - 1)  # open(t) -> open(t+1)
        _px = (O, RO)
    return _px


def simulate(sel, H, K=20, cost_bps=10.0, start=None, end=None, spy_bps=1.0):
    """sel: DataFrame with entry_idx, tk, score. Returns daily DataFrame (port, spy, n_active) on [start, end]."""
    O, RO = prices()
    dates = O.index
    i0 = dates.searchsorted(pd.Timestamp(start)) if start else 0
    i1 = dates.searchsorted(pd.Timestamp(end), side="right") - 1 if end else len(dates) - 2
    i1 = min(i1, len(dates) - 2)
    ro = RO.values; col = {t: j for j, t in enumerate(RO.columns)}
    spy = ro[:, col["SPY"]]
    sel = sel[sel.tk.isin(col.keys())].sort_values(["entry_idx", "score"], ascending=[True, False])
    by_day = {i: g for i, g in sel.groupby("entry_idx")}
    active = []  # list of (col, exit_idx)
    port, n_act, taken = [], [], 0
    prev_spy_w = 1.0
    for t in range(i0, i1 + 1):
        c = 0.0
        still = [(j, x) for (j, x) in active if x > t]
        c += (len(active) - len(still)) * cost_bps / 1e4 / K
        active = still
        if t in by_day:
            for r in by_day[t].itertuples():
                if len(active) >= K:
                    break
                j = col[r.tk]
                if np.isfinite(ro[t, j]) and all(j != a for a, _ in active):
                    active.append((j, t + H)); c += cost_bps / 1e4 / K; taken += 1
        w = 1.0 / K
        rs = np.nan_to_num(np.array([ro[t, j] for j, _ in active]), nan=0.0)
        spy_w = 1 - w * len(active)
        c += abs(spy_w - prev_spy_w) * spy_bps / 1e4
        prev_spy_w = spy_w
        port.append(w * rs.sum() + spy_w * spy[t] - c)
        n_act.append(len(active))
    out = pd.DataFrame({"port": port, "spy": spy[i0:i1 + 1], "n": n_act}, index=dates[i0:i1 + 1])
    out.attrs["taken"] = taken
    return out


def stats(d):
    yrs = len(d) / 252
    cagr = lambda r: (1 + r).prod() ** (1 / yrs) - 1
    eq = (1 + d.port).cumprod()
    return {"cagr": cagr(d.port), "spy": cagr(d.spy), "excess": cagr(d.port) - cagr(d.spy),
            "sharpe": d.port.mean() / d.port.std() * np.sqrt(252), "maxdd": (eq / eq.cummax() - 1).min(),
            "avg_n": d.n.mean(), "trades": d.attrs.get("taken", np.nan)}
