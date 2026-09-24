"""Shared model + backtest code (used identically by dev.py and test.py)."""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "round6" / "j03_fomc"

FEATS = {
    "a_notext": ["dy2_bp", "spy_day", "tlt_day"],
    "b_dict": ["dy2_bp", "spy_day", "tlt_day", "dict_net", "dict_dnet", "cos_prev", "dissents"],
    "c_jev": ["dy2_bp", "spy_day", "tlt_day", "dict_net", "dict_dnet", "cos_prev", "dissents",
              "J_hawk", "J_guid", "J_infl", "J_bs", "J_risk"],
}
ASSETS = ["SPY", "QQQ", "IWM", "TLT", "IEF", "SHY", "GLD", "CASH"]
EQ_SPLIT = {"SPY": 0.5, "QQQ": 0.25, "IWM": 0.25}
W_EQ_BASE, W_EQ_SLOPE, Z_BOND, GLD_SHARE = 0.6, 0.4, 0.5, 0.2
RIDGE_ALPHA_PER_N = 1.0   # ridge penalty = alpha * n_train on standardised features


def load_prices():
    px = pd.read_parquet(D / "prices.parquet")
    px["CASH_co"] = 0.0
    return px


def load_events():
    d = pd.read_parquet(D / "docs.parquet")
    j = pd.read_parquet(D / "jev_scores.parquet")
    d = d.merge(j.drop(columns=["raw"]), on=["kind", "release"], how="left")
    # same-day events: statements after minutes (the latest document wins at the rebalance)
    d["ord"] = d.kind.map({"M": 0, "S": 1})
    d = d.sort_values(["event_date", "ord"]).reset_index(drop=True)
    return d


def add_targets(ev, px):
    """Holding-period excess returns from the close of event i to the close of event i+1 (training targets only)."""
    idx = px.index
    cum = {a: np.log1p(px[a + "_cc"].fillna(0)).cumsum() for a in ["SPY", "TLT", "CASH"]}
    i0 = idx.get_indexer(ev.event_date)
    i1 = np.r_[i0[1:], -1]
    ev = ev.copy()
    ev["next_date"] = [idx[k] if k >= 0 else pd.NaT for k in i1]
    for a, name in (("SPY", "y_eq"), ("TLT", "y_dur")):
        ra = np.where(i1 >= 0, np.exp(cum[a].values[np.maximum(i1, 0)] - cum[a].values[i0]) - 1, np.nan)
        rc = np.where(i1 >= 0, np.exp(cum["CASH"].values[np.maximum(i1, 0)] - cum["CASH"].values[i0]) - 1, np.nan)
        ev[name] = (ra - rc) * 100
    return ev


def standardise(train, test, cols):
    """z-score within document kind, using training-set moments only; NaN -> 0."""
    Xtr, Xte = train[cols].astype(float).copy(), test[cols].astype(float).copy()
    for k in ["S", "M"]:
        mtr, mte = train.kind == k, test.kind == k
        mu, sd = Xtr[mtr].mean(), Xtr[mtr].std().replace(0, 1).fillna(1)
        Xtr.loc[mtr] = (Xtr[mtr] - mu) / sd
        Xte.loc[mte] = (Xte[mte] - mu) / sd
    return Xtr.fillna(0).clip(-4, 4).values, Xte.fillna(0).clip(-4, 4).values


def ridge_fit(X, y, alpha_per_n=RIDGE_ALPHA_PER_N):
    n, p = X.shape
    Xc = np.c_[np.ones(n), X]
    P = np.eye(p + 1) * alpha_per_n * n
    P[0, 0] = 0
    return np.linalg.solve(Xc.T @ Xc + P, Xc.T @ y)


def ridge_pred(b, X):
    return np.c_[np.ones(len(X)), X] @ b


def weights_from_z(z_eq, z_dur, gld_ok):
    w = dict.fromkeys(ASSETS, 0.0)
    weq = float(np.clip(W_EQ_BASE + W_EQ_SLOPE * z_eq, 0.0, 1.0))
    for a, s in EQ_SPLIT.items():
        w[a] = weq * s
    rest = 1 - weq
    g = GLD_SHARE * rest if gld_ok else 0.0
    bond = "TLT" if z_dur > Z_BOND else ("SHY" if z_dur < -Z_BOND else "IEF")
    w[bond] += rest - g
    w["GLD"] += g
    return w


def fit_models(train, cols, alpha_per_n=RIDGE_ALPHA_PER_N):
    tr = train.dropna(subset=["y_eq", "y_dur"])
    Xtr, _ = standardise(tr, tr.iloc[:1], cols)
    out = {}
    for t in ("y_eq", "y_dur"):
        b = ridge_fit(Xtr, tr[t].values, alpha_per_n)
        fit = ridge_pred(b, Xtr)
        out[t] = (b, fit.mean(), fit.std() if fit.std() > 1e-9 else 1.0)
    return out, tr


def predict_z(models, tr, rows, cols):
    _, Xte = standardise(tr, rows, cols)
    z = {}
    for t in ("y_eq", "y_dur"):
        b, mu, sd = models[t]
        z[t] = (ridge_pred(b, Xte) - mu) / sd
    return z


def walk_forward(ev, cols, start, end, min_train=60, alpha_per_n=RIDGE_ALPHA_PER_N, frozen=None):
    """For each event in [start, end]: fit on events whose target was realised by that event date, predict z.
    frozen=(models, tr): use fixed DEV coefficients instead of refitting."""
    rows = []
    for i, r in ev.iterrows():
        if r.event_date < pd.Timestamp(start) or r.event_date > pd.Timestamp(end):
            continue
        if frozen is not None:
            models, tr = frozen
        else:
            hist = ev[(ev.next_date <= r.event_date)]
            if len(hist) < min_train:
                continue
            models, tr = fit_models(hist, cols, alpha_per_n)
        z = predict_z(models, tr, ev.loc[[i]], cols)
        rows.append(dict(event_date=r.event_date, kind=r.kind, z_eq=z["y_eq"][0], z_dur=z["y_dur"][0],
                         y_eq=r.y_eq, y_dur=r.y_dur))
    return pd.DataFrame(rows)


def schedule(preds, px, neutral=False):
    """Target weights per event date (last event of the day wins)."""
    gld_first = px.GLD_px.eq(0).idxmax()
    out = {}
    for _, r in preds.iterrows():
        ze, zd = (0.0, 0.0) if neutral else (r.z_eq, r.z_dur)
        out[r.event_date] = weights_from_z(ze, zd, r.event_date >= gld_first)
    return pd.DataFrame(out).T.sort_index()[ASSETS]


def backtest(sched, px, start, end, cost_bp=3.0, execution="close", init=None):
    """Daily backtest. execution='close': trade at the event-day close. 'open': trade at next-day open
    (proxy era without opens: at next-day close). Costs: cost_bp per side on traded notional."""
    days = px.loc[start:end].index
    cc = px[[a + "_cc" for a in ASSETS]].loc[start:end].fillna(0).values
    co = px[[a + "_co" for a in ASSETS]].loc[start:end].values
    w = np.array([sched.iloc[0][a] for a in ASSETS]) if init is None else np.array([init[a] for a in ASSETS])
    pending = None
    nav, turn, rets = 1.0, 0.0, []
    sd = {d: sched.loc[d].values.astype(float) for d in sched.index}
    c = cost_bp / 1e4
    for k, day in enumerate(days):
        r_day = 0.0
        if pending is not None and execution == "open":
            if np.all(np.isfinite(co[k][pending > 0])) and np.all(np.isfinite(co[k][w > 0])):
                ov = np.nan_to_num(co[k])
                r_ov = w @ ov
                w_after = w * (1 + ov) / (1 + r_ov)
                tr = np.abs(pending - w_after).sum()
                intr = (1 + cc[k]) / (1 + ov) - 1
                r_day = (1 + r_ov) * (1 - c * tr) * (1 + pending @ intr) - 1
                w = pending * (1 + intr) / (1 + pending @ intr)
                turn += tr
                pending = None
                rets.append(r_day)
                nav *= 1 + r_day
                if day in sd:
                    pending = sd[day]
                continue
        r_day = w @ cc[k]
        w = w * (1 + cc[k]) / (1 + r_day)
        new = sd.get(day) if execution == "close" else (pending if pending is not None else None)
        if execution == "open" and pending is not None:   # fallback: no opens -> trade at this close
            tr = np.abs(pending - w).sum(); r_day = (1 + r_day) * (1 - c * tr) - 1; w = pending; turn += tr; pending = None
        if execution == "close" and new is not None:
            tr = np.abs(new - w).sum(); r_day = (1 + r_day) * (1 - c * tr) - 1; w = new; turn += tr
        if execution == "open" and day in sd:
            pending = sd[day]
        rets.append(r_day)
        nav *= 1 + r_day
    s = pd.Series(rets, index=days)
    return s, turn / max(len(days) / 252, 1e-9)


def static_60_40(px, start, end, cost_bp=3.0):
    """SPY/IEF 60/40, monthly rebalanced, trading at the month-end close."""
    days = px.loc[start:end].index
    me = set(pd.Series(days, index=days).groupby(days.to_period("M")).max())
    sched = pd.DataFrame([{**dict.fromkeys(ASSETS, 0.0), "SPY": 0.6, "IEF": 0.4} for _ in me], index=sorted(me))
    return backtest(sched, px, start, end, cost_bp, "close")


def metrics(r):
    r = r.dropna()
    yrs = len(r) / 252
    nav = (1 + r).cumprod()
    cagr = nav.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    dd = (nav / nav.cummax() - 1).min()
    return dict(CAGR=cagr * 100, vol=vol * 100, sharpe=(r.mean() * 252) / (r.std() * np.sqrt(252)), maxDD=dd * 100)
