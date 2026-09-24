"""Walk-forward models (feature sets a/b/c) + calendar-time portfolio simulation.
Usage: s09_backtest.py dev|test [cost_bp]
Walk-forward: for IPO-year Y, train on priced events whose exit < Jan 1 of Y; select test events whose
predicted P(beat SPY) >= 67th percentile of the in-sample training predictions."""
import sys, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from common import DATA, HERE

PERIOD = sys.argv[1] if len(sys.argv) > 1 else "dev"
COST = float(sys.argv[2]) / 1e4 if len(sys.argv) > 2 else 0.0040
YEARS = list(range(2012, 2019)) if PERIOD == "dev" else list(range(2019, 2027))
C_REG, Q_SEL = 0.3, 0.67

A = ["log_offer", "log_proceeds", "first_day_ret", "mom_0_25", "nasdaq", "f1", "hot90", "log_reg_days"]
KW = ["kw_netloss", "kw_accum_deficit", "kw_repay", "kw_pay_holders", "kw_sponsor", "kw_dual", "kw_controlled",
      "kw_mw", "kw_customer_conc", "kw_egc", "kw_going_concern", "kw_top_any", "kw_top_lead", "selling_only",
      "has_selling_holders", "best_efforts", "log_nrisk"]
JEV = ["j_profitable", "j_revenue", "j_uop_growth_capex_rnd", "j_uop_repay_debt", "j_uop_pay_existing_holders",
       "j_uop_acquisitions", "j_sponsor_venture_capital", "j_sponsor_private_equity", "j_sponsor_parent_corporation",
       "j_sponsor_founders_management", "j_insider_selling", "j_dual_class", "j_controlled", "j_material_weakness",
       "j_customer_conc", "j_lead_uw_bulge_bracket", "j_lead_uw_small_boutique", "j_biotech_preclinical",
       "j_going_concern", "j_foreign_ops"]
SETS = {"a_numeric": A, "b_keyword": A + KW, "c_jev": A + KW + JEV}
# literature rule (no fitting): quality points, buy if >= 3 of 5
def rule_jev(P):
    return ((P.j_profitable > .5).astype(int) + ((P.j_sponsor_venture_capital + P.j_sponsor_private_equity) > .5)
            + (P.j_lead_uw_bulge_bracket > .5) + ((P.j_uop_repay_debt + P.j_uop_pay_existing_holders) < .5)
            + (P.j_insider_selling < 1.5)) >= 3
def rule_kw(P):
    return ((~P.kw_netloss & ~P.kw_accum_deficit).astype(int) + P.kw_sponsor.astype(int) + P.kw_top_lead.astype(int)
            + (~P.kw_repay & ~P.kw_pay_holders).astype(int) + (~P.selling_only).astype(int)) >= 3


def load():
    P = pd.read_parquet(DATA / "panel.parquet")
    P["log_nrisk"] = np.log1p(P.kw_nrisk)
    for c in KW:
        if P[c].dtype == object:
            P[c] = P[c].astype(bool)
    P = P[~(P.px_signal < 5)]                      # tradability: price >= $5 at signal (unknown for missing names)
    if "j_spac" in P:
        P = P[~(P.j_spac > 0.5)]                   # Jev SPAC/blank-check screen (applied to every set)
    P = P[P.entry.notna()]
    P = P[P.has_px | (P.end_est > P.entry)]        # a missing name that stopped trading before entry cannot be bought
    return P.reset_index(drop=True)


def walk_forward(P, cols):
    out = pd.Series(np.nan, index=P.index); sel = pd.Series(False, index=P.index)
    for Y in YEARS:
        tr = P[P.has_px & P.y.notna() & (P.exit < pd.Timestamp(f"{Y}-01-01"))]
        te = P[P.year == Y]
        if len(tr) < 60 or len(te) == 0:
            continue
        X = tr[cols].astype(float); med = X.median(); mu = X.fillna(med).mean(); sd = X.fillna(med).std().replace(0, 1)
        z = lambda D: ((D[cols].astype(float).fillna(med) - mu) / sd).clip(-5, 5).values
        lr = LogisticRegression(C=C_REG, max_iter=2000).fit(z(tr), tr.y.values)
        thr = np.quantile(lr.predict_proba(z(tr))[:, 1], Q_SEL)
        p = lr.predict_proba(z(te))[:, 1]
        out[te.index] = p; sel[te.index] = p >= thr
    return out, sel


def simulate(P, pick, scen, cost, bench):
    """Calendar-time EW portfolio of picked events. scen: surv | m50 | m100 | refined."""
    E = P[pick].copy()
    if scen == "surv":
        E = E[E.has_px]
    elif scen == "refined":
        E = E[E.has_px | (E.dies_in_hold & ~E.acquired) | (E.dies_in_hold & E.acquired)]
    cal = bench.index
    start = E.entry.min(); end = min(E.exit.max() if E.exit.notna().any() else cal[-1], cal[-1])
    days = cal[(cal >= start) & (cal <= end)]
    rets = {}
    for r in E.itertuples():
        x = r.exit if pd.notna(r.exit) else cal[-1]
        d = days[(days >= r.entry) & (days < x)]
        if len(d) == 0:
            continue
        if r.has_px:
            o = pd.read_parquet(DATA / "prices" / f"{r.acc}.parquet").open
            o = o.reindex(cal).ffill()
            rr = (o.shift(-1) / o - 1).reindex(d).fillna(0.0)
        else:
            loss = {"m50": -0.5, "m100": -1.0}.get(scen)
            if scen == "refined":
                loss = 0.0 if r.acquired else -1.0
            rr = pd.Series(0.0, index=d)
            dd = d[d <= r.end_est]
            rr.iloc[len(dd) - 1 if len(dd) else -1] = loss
        rets[r.acc] = rr
    R = pd.DataFrame(rets).reindex(days)
    active = R.notna()
    R = R.fillna(0.0).values; act = active.values
    w = np.zeros(R.shape[1]); prev = np.zeros(R.shape[1], bool); nav = [1.0]; turn = []
    for t in range(len(days)):
        a = act[t]
        if (a != prev).any():
            tgt = np.where(a, 1.0 / max(a.sum(), 1), 0.0)
            to = np.abs(tgt - w).sum(); w = tgt
        else:
            to = 0.0
        g = (w * R[t]).sum()
        pr = g - cost * to
        nav.append(nav[-1] * (1 + pr)); turn.append(to)
        gross = 1 + g
        w = w * (1 + R[t]) / gross if gross > 0 else w * 0
        w = np.where(a, w, 0.0); prev = a
    nav = pd.Series(nav[1:], index=days)
    return nav, np.sum(turn), active.sum(axis=1)


def stats(nav):
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    mdd = (nav / nav.cummax() - 1).min()
    return cagr, mdd


if __name__ == "__main__":
    P = load()
    bench = pd.read_parquet(DATA / "bench.parquet").ffill()
    P = P[P.year.isin(YEARS)] if PERIOD == "test" else P[P.year <= 2018]
    Pall = load()
    res, picks = [], {}
    for name, cols in SETS.items():
        cols = [c for c in cols if c in Pall]
        p, s = walk_forward(Pall, cols)
        Pall[f"p_{name}"] = p; Pall[f"sel_{name}"] = s
    if "j_profitable" in Pall:
        Pall["sel_rule_jev"] = rule_jev(Pall); Pall["sel_rule_kw"] = rule_kw(Pall)
    else:
        Pall["sel_rule_kw"] = rule_kw(Pall)
    Pall["sel_all"] = True
    Q = Pall[Pall.year.isin(YEARS)]
    Q = Q[Q.p_a_numeric.notna()] if Q.p_a_numeric.notna().any() else Q
    Q.to_parquet(DATA / f"wf_{PERIOD}.parquet")
    ev = []
    for k in [c for c in Q if c.startswith("sel_")]:
        S = Q[Q[k]]; Sp = S[S.has_px & S.ret.notna()]
        pk = "p_" + k[4:]
        auc = roc_auc_score(Q[Q.y.notna()].y, Q[Q.y.notna()][pk]) if pk in Q and Q.y.notna().sum() > 20 else np.nan
        ev.append(dict(sel=k[4:], n=len(S), frac_px=S.has_px.mean(), n_priced=len(Sp), mean_ret=Sp.ret.mean(),
                       mean_xs_spy=Sp.xs_spy.mean(), med_xs=Sp.xs_spy.median(), hit=(Sp.xs_spy > 0).mean(),
                       fail_rate=(S.dies_in_hold & ~S.acquired).mean(), acq_rate=(S.dies_in_hold & S.acquired).mean(), auc=auc))
    ev = pd.DataFrame(ev); print(ev.round(3).to_string())
    port = []
    for k in [c for c in Q if c.startswith("sel_")]:
        for scen in ["surv", "refined", "m50", "m100"]:
            for cm in [1, 2]:
                nav, to, nact = simulate(Q, Q[k], scen, COST * cm, bench)
                cg, mdd = stats(nav)
                d0, d1 = nav.index[0], nav.index[-1]
                bc = {b: stats(bench[f"{b}_adj"].loc[d0:d1].dropna())[0] for b in ["SPY", "IWM"]}
                ipo = bench["IPO_adj"].loc[max(d0, pd.Timestamp("2013-10-16")):d1].dropna()
                port.append(dict(sel=k[4:], scen=scen, cost_x=cm, start=d0.date(), end=d1.date(), cagr=cg, mdd=mdd,
                                 spy=bc["SPY"], iwm=bc["IWM"], ipo_etf=stats(ipo)[0] if len(ipo) > 250 else np.nan,
                                 vs_spy=cg - bc["SPY"], turnover=to, avg_n=nact.mean()))
                if scen == "surv" and cm == 1:
                    nav.to_frame("nav").to_parquet(DATA / f"nav_{PERIOD}_{k[4:]}.parquet")
    port = pd.DataFrame(port); print(port.round(3).to_string())
    ev.to_csv(HERE / f"results_{PERIOD}_events.csv", index=False)
    port.to_csv(HERE / f"results_{PERIOD}_portfolio.csv", index=False)
