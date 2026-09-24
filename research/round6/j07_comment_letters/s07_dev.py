"""DEV analysis (letters disseminated 2012-2019). usage: s07_dev.py
1. Event study: 3/6/12-month excess returns (vs EW S&P 500) by rule flag, Jev topic and severity bucket
   (simple t and month-clustered t).
2. Walk-forward logistic models for the three nested feature sets (A no text, B + keywords, C + Jev), target
   1[12-month excess return < 0]; fold year Y in 2014..2019 is trained only on events whose 12-month label window
   ended before Jan 1 of Y. OOS AUC, rank IC, top-quintile spread, paired bootstrap of AUC(C) - AUC(B).
3. Overlays: EW universe minus flagged names (12-month exclusion), momentum top-50 minus flagged names, and
   clean-closer portfolios. Costs 5/10/20 bp per side.
Outputs: OUT/dev_*.csv, DATA/dev_oos_scores.parquet, DATA/events_feat.parquet."""
import sys
from common import *
from features import build_sets, jev_event_features, rule_flags
from questions import TOPICS
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from s06_leak import auc
import bt

C_REG = 1.0
TOPQ = 0.8  # flag = predicted risk above the 80th percentile of the training predictions


def load_events():
    E = pd.read_parquet(DATA / "events.parquet")
    L = pd.read_parquet(DATA / "letters.parquet", columns=["acc", "cik", "dissem", "pos", "n_in_event"])
    J = pd.read_parquet(DATA / "jev_v1.parquet")
    JE = jev_event_features(L, J)
    E = E.merge(JE, on=["cik", "dissem"], how="left")
    cal = bt.CL["SPY"].dropna().index
    i = cal.searchsorted(E.dissem.values, side="right") + 252
    E["label_end"] = [cal[k] if k < len(cal) else pd.Timestamp("2100-01-01") for k in i]
    E["y"] = (E.x252 < 0).astype(float).where(E.x252.notna())
    E = pd.concat([E, rule_flags(E)], axis=1)
    return E


def fit_predict(Xtr, ytr, Xte):
    sc = StandardScaler().fit(Xtr)
    m = LogisticRegression(C=C_REG, max_iter=5000).fit(sc.transform(Xtr), ytr)
    return m.predict_proba(sc.transform(Xtr))[:, 1], m.predict_proba(sc.transform(Xte))[:, 1], m, sc


def walk_forward(E, sets, years, period_mask):
    rows = []
    for Y in years:
        tr = period_mask & E.y.notna() & (E.label_end < pd.Timestamp(f"{Y}-01-01"))
        te = period_mask & (E.dissem.dt.year == Y)
        for name, X in sets.items():
            ptr, pte, _, _ = fit_predict(X[tr].values, E.y[tr].values, X[te].values)
            thr = np.quantile(ptr, TOPQ)
            rows.append(pd.DataFrame({"idx": E.index[te], "set": name, "risk": pte, "flag": (pte >= thr).astype(int),
                                      "fold": Y, "n_train": tr.sum()}))
    return pd.concat(rows)


def event_table(E, groups, H=(63, 126, 252)):
    out = []
    for gname, mask in groups:
        s = E[mask]
        row = {"group": gname, "N": len(s)}
        for h in H:
            x = s[f"x{h}"].dropna()
            row[f"x{h}_mean%"] = x.mean() * 100
            row[f"x{h}_t"] = x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan
            mm = s.assign(mo=s.dissem.dt.to_period("M")).groupby("mo")[f"x{h}"].mean().dropna()
            row[f"x{h}_tclust"] = mm.mean() / mm.std() * np.sqrt(len(mm)) if len(mm) > 2 else np.nan
        out.append(row)
    return pd.DataFrame(out).set_index("group")


def overlay_runs(E, flag_cols, months, clean_cols=(), mom=None):
    mem = bt.member_sets()
    res, series = [], {}
    base = bt.simulate(mem, months)
    series["EW_base"] = base
    ew_b = base["net_10bp"]
    for name, sims in [("EW_base", base)]:
        pass
    variants = {}
    for fc in flag_cols:
        ex = bt.exclusion_sets(E, fc)
        variants[f"EW_minus_{fc}"] = {me: [t for t in mem.get(me, []) if t not in ex[me]] for me in months}
        if mom is not None:
            variants[f"MOM50_minus_{fc}"] = {me: mom_top(mom, me, mem, ex[me]) for me in months}
    if mom is not None:
        variants["MOM50_base"] = {me: mom_top(mom, me, mem, set()) for me in months}
    for cc in clean_cols:
        inc = bt.exclusion_sets(E, cc)
        variants[f"HOLD_{cc}"] = {me: [t for t in mem.get(me, []) if t in inc[me]] for me in months}
    for v, h in variants.items():
        series[v] = bt.simulate(h, months)
    for v, s in series.items():
        bench = series["MOM50_base"]["net_10bp"] if v.startswith("MOM50_minus") else ew_b
        for c in ["net_5bp", "net_10bp", "net_20bp"]:
            bmk = (series["MOM50_base"][c] if v.startswith("MOM50_minus") else series["EW_base"][c])
            st = bt.stats(s[c], bmk)
            st.update({"variant": v, "cost": c, "avg_n": s["n"].mean(), "turnover_m": s["turnover"].mean()})
            res.append(st)
    return pd.DataFrame(res), series


def mom_top(mom, me, mem, excl, k=50):
    if me not in mom.index:
        return []
    s = mom.loc[me].reindex([t for t in mem.get(me, []) if t not in excl]).dropna()
    return list(s.sort_values(ascending=False).index[:k])


def main():
    E = load_events()
    E = E[E.has_px].reset_index(drop=True)
    dev = E.period == "DEV"
    print("DEV events with prices:", dev.sum(), "Jev-scored:", E[dev].jv_scored.gt(0).mean().round(3))
    E.to_parquet(DATA / "events_feat.parquet")
    D = E[dev]

    # ---- 1. event study ----
    groups = [("all events", D.index == D.index)]
    for c in ["R_A_long_review", "R_K_restate_kw", "R_J_high_sev", "CC_A_single", "CC_K_clean", "CC_J_clean"]:
        groups.append((c, D[c] == 1))
    for k in list(TOPICS) + ["none"]:
        groups.append((f"topic={k}", D.jv_topic == k))
    for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 5)]:
        groups.append((f"sev_max in [{lo},{hi})", D.jv_sev_max.between(lo, hi - 1e-9)))
    groups.append(("jv_restate_max>=0.5", D.jv_restate_max >= 0.5))
    groups.append(("jv_repeat_max>=0.5", D.jv_repeat_max >= 0.5))
    for c in ["revenue_recognition", "non_gaap", "going_concern_or_liquidity"]:
        groups.append((f"kw {c}", D[{"revenue_recognition": "sum_kw_rev", "non_gaap": "sum_kw_nongaap",
                                      "going_concern_or_liquidity": "sum_kw_gc"}[c]] >= 2))
    T = event_table(D, groups)
    T.round(3).to_csv(OUT / "dev_event_study.csv")
    print(md(T.round(2), "{:.2f}"))

    # ---- 2. walk-forward models ----
    sets = build_sets(E)
    P = walk_forward(E, sets, range(2014, 2020), dev)
    P.to_parquet(DATA / "dev_oos_scores.parquet")
    rows = []
    rng = np.random.default_rng(0)
    for name, g in P.groupby("set"):
        e = E.loc[g.idx]
        ok = e.y.notna().values
        r, y, x = g.risk.values[ok], e.y.values[ok], e.x252.values[ok]
        top = g.flag.values[ok] == 1
        rows.append({"set": name, "N_oos": ok.sum(), "AUC": auc(r, y),
                     "rankIC": pd.Series(r).corr(pd.Series(-x), method="spearman"),
                     "flag_share": top.mean(), "x252_flagged%": x[top].mean() * 100, "x252_rest%": x[~top].mean() * 100})
    MR = pd.DataFrame(rows).set_index("set")
    # paired bootstrap AUC(C)-AUC(B), AUC(B)-AUC(A)
    piv = P.pivot_table(index="idx", columns="set", values="risk")
    yy = E.loc[piv.index, "y"]
    piv = piv[yy.notna()]; yy = yy[yy.notna()].values
    dif = {"C-B": [], "B-A": [], "C-A": []}
    for _ in range(1000):
        i = rng.integers(0, len(piv), len(piv))
        a = {s: auc(piv[s].values[i], yy[i]) for s in piv.columns}
        dif["C-B"].append(a["C_jev"] - a["B_keywords"]); dif["B-A"].append(a["B_keywords"] - a["A_notext"])
        dif["C-A"].append(a["C_jev"] - a["A_notext"])
    for k, v in dif.items():
        print(f"AUC {k}: mean {np.mean(v):+.4f}  95% CI [{np.percentile(v, 2.5):+.4f}, {np.percentile(v, 97.5):+.4f}]")
    MR.round(4).to_csv(OUT / "dev_models.csv")
    pd.DataFrame({k: [np.mean(v), np.percentile(v, 2.5), np.percentile(v, 97.5)] for k, v in dif.items()},
                 index=["mean", "lo95", "hi95"]).T.round(4).to_csv(OUT / "dev_auc_diff.csv")
    print(md(MR.round(4), "{:.4f}"))
    # coefficient view (all DEV with labels ending before 2020), for importance
    tr = dev & E.y.notna() & (E.label_end < pd.Timestamp("2020-01-01"))
    X = sets["C_jev"]
    _, _, m, sc = fit_predict(X[tr].values, E.y[tr].values, X[tr].values[:5])
    coef = pd.Series(m.coef_[0], index=X.columns).sort_values()
    coef.round(4).to_csv(OUT / "dev_coef_C.csv")
    print("C coefficients (std. units, + = more likely to underperform):\n", coef.round(3).to_string())

    # ---- 3. overlays ----
    for s in ["A_notext", "B_keywords", "C_jev"]:
        g = P[P.set == s].set_index("idx")
        E[f"M_{s}"] = 0
        E.loc[g.index, f"M_{s}"] = g.flag.values
    months_all = [m for m in bt.M.month_end if pd.Timestamp("2012-01-31") <= m <= pd.Timestamp("2019-11-30")]
    months_m = [m for m in months_all if m >= pd.Timestamp("2014-12-31")]
    mom = bt.momentum_table()
    Ed = E[dev]
    R1, _ = overlay_runs(Ed, ["R_A_long_review", "R_K_restate_kw", "R_J_high_sev"], months_all,
                         clean_cols=["CC_A_single", "CC_K_clean", "CC_J_clean"], mom=mom)
    R1["window"] = "2012-01..2019-12"
    R2, _ = overlay_runs(Ed, ["M_A_notext", "M_B_keywords", "M_C_jev", "R_J_high_sev"], months_m, mom=mom)
    R2["window"] = "2015-01..2019-12 (OOS model flags)"
    RR = pd.concat([R1, R2])
    RR.to_csv(OUT / "dev_overlays.csv", index=False)
    show = RR[RR.cost == "net_10bp"][["window", "variant", "CAGR", "vs_bench_pts", "diff_t", "vs_SPY_pts", "maxDD",
                                       "avg_n", "turnover_m"]]
    print(md(show.set_index("variant").round(4), "{:.4f}"))


if __name__ == "__main__":
    main()
