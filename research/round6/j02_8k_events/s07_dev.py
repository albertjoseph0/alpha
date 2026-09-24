"""DEV analysis (2019-10..2022-12 only). Rule-based event studies and walk-forward models for feature sets
(a) items+price, (b) + LM/keywords, (c) + Jev. Usage: s07_dev.py VERSION"""
import sys, json, warnings
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from common import DATA, ITEMS, DEV, RES
from s06_panel import build
import bt
warnings.filterwarnings("ignore")

ver = sys.argv[1]
P = build(ver if ver != "base" else "")
P["tk"] = P.ticker.str.replace(".", "-", regex=False)
D = P[(P.filingDate >= DEV[0]) & (P.filingDate <= DEV[1])].copy()
HS = [5, 10, 20, 40, 60]
ICOL = ["i" + i.replace(".", "") for i in ITEMS]
FA = ICOL + ["n_items", "has_ex99", "has_ex10", "has_ex2", "after_hours", "ret5", "ret21", "ret63", "vol63",
             "dvol63", "hi252", "sret21"]
FB = FA + ["lm_pos", "lm_neg", "lm_pol", "n_words"] + [c for c in P.columns if c.startswith("kw_")]
JF = [c for c in P.columns if c.startswith("j_")]
FC = FB + JF
D["n_words"] = np.log1p(D.n_words)
have = D[JF[0]].notna() if JF else D.acc.notna()
print("DEV events", len(D), "with Jev", int(have.sum()), "with price", int(D.entry_date.notna().sum()))
D = D[have & D.entry_date.notna()].copy()


def ev_stats(g, h):
    x = g[f"ar{h}"].dropna()
    if len(x) < 5:
        return dict(n=len(x), mean=np.nan, med=np.nan, t=np.nan)
    m = g.assign(w=g.entry_date.dt.to_period("W")).groupby("w")[f"ar{h}"].mean().dropna()
    return dict(n=len(x), mean=100 * x.mean(), med=100 * x.median(), t=m.mean() / m.std() * np.sqrt(len(m)) if len(m) > 2 else np.nan)


out = {}
# ---------- 1. pre-specified rules (no fitting) ----------
if JF:
    rules = {
        "jev_pos": (D.j_tone >= 2.5) & (D.j_magnitude >= 1.5) & (D.j_routine < 0.5) & (D.j_target < 0.5),
        "jev_pos_strong": (D.j_tone >= 3.0) & (D.j_magnitude >= 2.0) & (D.j_routine < 0.5) & (D.j_target < 0.5),
        "jev_neg": (D.j_tone <= 1.5) & (D.j_routine < 0.5),
        "jev_bad_mandatory": D.j_bad_mandatory >= 0.5,
        "jev_exec_sudden": D.j_exec_sudden >= 0.5,
        "jev_exec_planned": D.j_exec_planned >= 0.5,
        "jev_ceo_external": D.j_ceo_external >= 0.5,
        "jev_buyback": D.j_buyback >= 0.5,
        "jev_demand_bigcp": (D.j_demand >= 0.5) & (D.j_big_counterparty >= 0.5),
        "jev_guid_raised": D.j_guidance_raised >= 0.5,
        "jev_guid_lowered": (D.j_guidance_lowered + D.j_guidance_withdrawn) >= 0.5,
        "jev_target": D.j_target >= 0.5,
        "jev_dilution": D.j_dilution >= 0.5,
        "jev_cuts": D.j_cuts >= 0.5,
        "jev_activism": D.j_activism >= 0.5,
        "jev_strategic_review": D.j_strategic_review >= 0.5,
    }
    for c in [c for c in D.columns if c.startswith("jch_category")]:
        for v in D[c].dropna().unique():
            rules[f"cat_{v}"] = D[c] == v
else:
    rules = {}
b = lambda c: D[c].fillna(0) > 0
rules.update({
    "all": D.acc.notna(),
    "kw_pos": (b("kw_buyback") | b("kw_contract") | b("kw_g_raise") | b("kw_div_up")) & (D.lm_pol > 0) & ~b("kw_target"),
    "kw_neg": (b("kw_g_lower") | b("kw_investig") | b("kw_delist") | b("kw_layoff")) & (D.lm_pol < 0),
    "kw_exec_sudden": (b("kw_immediate") | b("kw_other_int")) & (b("kw_ceo") | b("kw_cfo")) & (D.i502 == 1),
    "lm_pos_top": D.lm_pol >= D.lm_pol.quantile(0.8),
    "lm_neg_top": D.lm_pol <= D.lm_pol.quantile(0.2),
})
rows = []
for k, m in rules.items():
    g = D[m]
    r = {"rule": k}
    for h in [5, 20, 60]:
        s = ev_stats(g, h); r["n"] = s["n"] if h == 5 else r["n"]; r[f"ar{h}"] = s["mean"]; r[f"t{h}"] = s["t"]
    rows.append(r)
RT = pd.DataFrame(rows).round(2)
RT.to_csv(RES / f"dev_rules_{ver}.csv", index=False)
print(RT.to_string())

# ---------- 2. walk-forward models ----------
FOLDS = [("2021-01-01", "2021-07-01"), ("2021-07-01", "2022-01-01"), ("2022-01-01", "2022-07-01"), ("2022-07-01", "2023-01-01")]
dates = bt.prices()[0].index


def fit(tr, feats, h):
    m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.03, max_depth=3, min_samples_leaf=100,
                                      l2_regularization=1.0, random_state=0)
    y = tr[f"ar{h}"].clip(-0.3, 0.3)
    m.fit(tr[feats], y)
    return m


res, sims = [], {}
for name, feats in [("A", FA), ("B", FB), ("C", FC)]:
    if name == "C" and not JF:
        continue
    for h in HS:
        oof = []
        for vs, ve in FOLDS:
            cut = dates.searchsorted(pd.Timestamp(vs))
            tr = D[(D.entry_idx + h < cut) & D[f"ar{h}"].notna()]
            va = D[(D.entry_date >= vs) & (D.entry_date < ve)].copy()
            m = fit(tr, feats, h)
            ref = tr[tr.entry_date >= pd.Timestamp(vs) - pd.Timedelta(days=365)]
            thr = np.quantile(m.predict(ref[feats]), 0.9)
            va["score"] = m.predict(va[feats]); va["thr"] = thr
            oof.append(va)
        O = pd.concat(oof)
        ok = O[f"ar{h}"].notna()
        ic = spearmanr(O.score[ok], O[f"ar{h}"][ok]).correlation
        sel = O[O.score >= O.thr]
        s = ev_stats(sel, h)
        sim = bt.simulate(sel, h, K=20, cost_bps=10, start="2021-01-01", end="2022-12-31")
        st = bt.stats(sim)
        sim2 = bt.simulate(sel, h, K=20, cost_bps=20, start="2021-01-01", end="2022-12-31")
        res.append({"set": name, "h": h, "ic": ic, "n_sel": s["n"], "sel_ar": s["mean"], "sel_t": s["t"],
                    "all_ar": 100 * O[f"ar{h}"].mean(), "cagr": st["cagr"], "spy": st["spy"], "excess": st["excess"],
                    "excess_2x": bt.stats(sim2)["excess"], "maxdd": st["maxdd"], "avg_n": st["avg_n"]})
        print(res[-1], flush=True)
        O[["acc", "entry_date", "score", "thr", f"ar{h}"]].to_parquet(DATA / f"oof_{ver}_{name}_{h}.parquet")
W = pd.DataFrame(res)
W.to_csv(RES / f"dev_models_{ver}.csv", index=False)
print(W.round(4).to_string())
