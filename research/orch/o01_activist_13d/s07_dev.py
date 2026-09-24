"""DEV analysis (filings 2014-2019 only; TEST rows are dropped on load and never touched here).

  s07_dev.py study   -> dev_results/event_study.csv : mean excess return (vs IWM) by Jev intent / filer type / keyword
  s07_dev.py rules   -> dev_results/rules.csv       : calendar-time portfolios of a few pre-listed rules, 2014-2019
  s07_dev.py ml      -> dev_results/ml.csv          : walk-forward (2016-2019 OOS, purged) nested models A / B / C
  s07_dev.py probe   -> dev_results/probe.csv       : leakage-probe AUCs
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import D, DEV, R, backtest, load_close, stats
from s06_features import A_COLS, B_COLS, KW

OUT = R / "dev_results"
HS = (21, 63, 126, 252)
INTENTS = ["passive", "engagement", "board", "sale", "capital_return", "operational", "buyout", "insider_or_deal"]
FILERS = ["hedge_fund", "private_equity", "operating_company", "individual", "financial_institution", "other"]
J_COLS = ([f"intent_p_{k}" for k in INTENTS] + ["hostility", "letter_sent", "undervalued", "agreement", "specific_demand"]
          + [f"filer_type_p_{k}" for k in FILERS])
C_COLS = B_COLS + J_COLS
SETS = {"A_notext": A_COLS, "B_keywords": B_COLS, "C_jev": C_COLS}
DEMAND = ["board", "sale", "capital_return", "operational"]


def load(close=None, period=DEV):
    p = pd.read_parquet(D / "panel.parquet")
    j = pd.read_parquet(D / "jev.parquet")
    j = j[j.get("error").isna()] if "error" in j else j
    p = p.merge(j.drop(columns=[c for c in ["error"] if c in j]), on="rep_adsh", how="inner")
    p = p[(p["file_date"] >= period[0]) & (p["file_date"] <= period[1])].copy()
    for h in HS:
        p[f"x{h}"] = p[f"r{h}"] - p[f"iwm{h}"]
        p[f"xs{h}"] = p[f"r{h}"] - p[f"spy{h}"]
    close = load_close() if close is None else close
    cal = close.index[close["SPY"].notna()]
    pos = cal.searchsorted(p["entry_date"])
    for h in HS:
        p[f"exit{h}"] = [cal[min(i + h, len(cal) - 1)] for i in pos]
    p["activist"] = p["intent"].isin(DEMAND)
    p["demand_p"] = p[[f"intent_p_{k}" for k in DEMAND]].sum(axis=1)
    p["kw_activist"] = ((p[["kw_board", "kw_sale", "kw_capital", "kw_oper", "kw_undervalued", "kw_letter", "kw_hostile"]].sum(axis=1) > 0)
                        & (p["kw_deal"] == 0)).astype(int)
    return p.reset_index(drop=True)


def tstat(x):
    x = x.dropna()
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def study():
    p = load()
    groups = {"all": p.index == p.index}
    for k in INTENTS:
        groups[f"intent={k}"] = p["intent"] == k
    groups["intent in demand4"] = p["activist"]
    for k in FILERS:
        groups[f"filer={k}"] = p["filer_type"] == k
    groups["demand4 & hedge_fund"] = p["activist"] & (p["filer_type"] == "hedge_fund")
    groups["hostility>=2"] = p["hostility"] >= 2
    for k in ["letter_sent", "undervalued", "agreement", "specific_demand"]:
        groups[f"{k}>0.5"] = p[k] > 0.5
    for k in list(KW) + ["kw_activist", "fn_fund", "fn_person", "spac"]:
        groups[f"{k}=1"] = p[k] == 1
    rows = []
    for g, m in groups.items():
        s = p[m]
        row = {"group": g, "n": len(s), "react_mean": s["react"].mean(), "pre20_mean": s["ret_m20"].mean()}
        for h in HS:
            x = s[f"x{h}"].dropna()
            row[f"x{h}_mean"] = x.mean()
            row[f"x{h}_med"] = x.median()
            row[f"x{h}_t"] = tstat(x)
            row[f"x{h}_wins"] = x.clip(*p[f"x{h}"].quantile([0.01, 0.99])).mean()
            row[f"x{h}_hit"] = (x > 0).mean()
        rows.append(row)
    out = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    out.to_csv(OUT / "event_study.csv", index=False)
    pd.set_option("display.width", 250)
    print(out[["group", "n", "react_mean", "x63_mean", "x63_t", "x126_mean", "x126_t", "x126_wins", "x126_med", "x252_mean", "x252_t", "x252_wins"]]
          .round(3).to_string())


RULES = {
    "R0_all_text_events": lambda p: p.index == p.index,
    "R1_kw_activist": lambda p: p["kw_activist"] == 1,
    "R2_jev_demand4": lambda p: p["activist"],
    "R3_jev_demand4_hedgefund": lambda p: p["activist"] & (p["filer_type"] == "hedge_fund"),
}


def run_rules(p, close, period, rules=RULES, hs=(63, 126, 252), cms=(1.0, 2.0)):
    bench = {"SPY": close["SPY"], "IWM": close["IWM"]}
    rows = []
    for name, fn in rules.items():
        sel = p[fn(p)]
        for h in hs:
            for cm in cms:
                nav, info = backtest(sel, close, h, period[0], period[1], cost_mult=cm)
                st = stats(nav, bench)
                rows.append({"rule": name, "H": h, "cost_x": cm, "n_events": len(sel), **info, **st})
                print(name, h, cm, len(sel), f"cagr {st['cagr']:.3f} spy {st['SPY_cagr']:.3f} iwm {st['IWM_cagr']:.3f} "
                      f"xSPY {st['x_SPY']:+.3f} alphaIWM {st['alpha_IWM']:+.3f} t {st['alpha_t_IWM']:.2f} dd {st['maxdd']:.2f}", flush=True)
    return pd.DataFrame(rows)


def rules():
    close = load_close()
    p = load(close)
    out = run_rules(p, close, DEV)
    OUT.mkdir(exist_ok=True)
    out.to_csv(OUT / "rules.csv", index=False)


def model(kind):
    if kind == "logit":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000))
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=50, random_state=0)


def walk_forward(p, cols, H, kind, years=(2016, 2017, 2018, 2019)):
    """OOS score per event; training uses only events whose exit is before the test year (purged)."""
    score = pd.Series(np.nan, index=p.index)
    thr = pd.Series(np.nan, index=p.index)
    y = (p[f"x{H}"] > 0).astype(int)
    for Y in years:
        t0 = pd.Timestamp(f"{Y}-01-01")
        tr = p[(p[f"exit{H}"] < t0) & p[f"x{H}"].notna()]
        te = p[(p["file_date"] >= t0) & (p["file_date"] < pd.Timestamp(f"{Y + 1}-01-01"))]
        m = model(kind).fit(tr[cols].fillna(0), y[tr.index])
        score[te.index] = m.predict_proba(te[cols].fillna(0))[:, 1]
        thr[te.index] = np.quantile(m.predict_proba(tr[cols].fillna(0))[:, 1], 2 / 3)
    return score, thr


def ml():
    close = load_close()
    p = load(close)
    bench = {"SPY": close["SPY"], "IWM": close["IWM"]}
    rows, imp = [], []
    oos = p[p["file_date"] >= "2016-01-01"]
    for kind in ("logit", "hgb"):
        for H in (63, 126, 252):
            for sname, cols in SETS.items():
                s, thr = walk_forward(p, cols, H, kind)
                o = oos.assign(score=s[oos.index], thr=thr[oos.index])
                ok = o[f"x{H}"].notna()
                auc = roc_auc_score((o.loc[ok, f"x{H}"] > 0), o.loc[ok, "score"])
                ic = spearmanr(o.loc[ok, "score"], o.loc[ok, f"x{H}"]).statistic
                sel = o[o["score"] >= o["thr"]]
                row = {"model": kind, "H": H, "set": sname, "n_oos": len(o), "auc": auc, "ic": ic, "n_sel": len(sel),
                       "sel_x_mean": sel[f"x{H}"].mean(), "sel_x_wins": sel[f"x{H}"].clip(*o[f"x{H}"].quantile([.01, .99])).mean(),
                       "all_x_mean": o[f"x{H}"].mean()}
                for cm in (1.0, 2.0):
                    nav, info = backtest(sel, close, H, "2016-01-01", DEV[1], cost_mult=cm)
                    st = stats(nav, bench)
                    row.update({f"cagr_c{cm:g}": st["cagr"], f"xSPY_c{cm:g}": st["x_SPY"], f"xIWM_c{cm:g}": st["x_IWM"],
                                f"alphaIWM_c{cm:g}": st["alpha_IWM"], f"alphaT_c{cm:g}": st["alpha_t_IWM"], f"dd_c{cm:g}": st["maxdd"]})
                rows.append(row)
                print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
                if kind == "logit" and sname == "C_jev":
                    m = model("logit").fit(p[p[f"exit{H}"] < pd.Timestamp("2020-01-01")][cols].fillna(0),
                                           (p[p[f"exit{H}"] < pd.Timestamp("2020-01-01")][f"x{H}"] > 0).astype(int))
                    coef = pd.Series(m[-1].coef_[0], index=cols)
                    imp.append(coef.rename(f"H{H}"))
    OUT.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "ml.csv", index=False)
    if imp:
        pd.concat(imp, axis=1).to_csv(OUT / "ml_coef_C_logit.csv")
        print(pd.concat(imp, axis=1).round(3).sort_values("H126").to_string())
    # the same three rules over the walk-forward OOS window, for a like-for-like comparison
    rr = run_rules(oos, close, ("2016-01-01", DEV[1]), hs=(63, 126, 252), cms=(1.0,))
    rr.to_csv(OUT / "rules_2016_2019.csv", index=False)


def probe():
    p = load()
    pr = pd.read_parquet(D / "probe.parquet").merge(p[["rep_adsh", "xs252", "x252"]], on="rep_adsh")
    pr = pr.dropna(subset=["xs252"])
    rows = []
    for col in ("probe_anon", "probe_named"):
        for tgt in ("xs252", "x252"):
            y = pr[tgt] > 0
            rows.append({"probe": col, "target": tgt, "n": len(pr), "auc": roc_auc_score(y, pr[col]),
                         "mean_p": pr[col].mean(), "base_rate": y.mean()})
    out = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    out.to_csv(OUT / "probe.csv", index=False)
    print(out.round(3).to_string())


if __name__ == "__main__":
    {"study": study, "rules": rules, "ml": ml, "probe": probe}[sys.argv[1]]()
