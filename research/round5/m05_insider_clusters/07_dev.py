"""Round 5b DEV analysis (events FILED 2006-2015 only).   usage: python 07_dev.py [prep|rules|ml|all]

prep : price matching for every v2 event (05_backtest.prepare) -> prepared_v2.pkl (via 06)
rules: (A) rules-based variants and (B) the same with Jev-based purchase filters, identical dates
ml   : logistic regression on DEV events, A features vs A+Jev vs A+dictionary, walk-forward by year
"""
import sys, os, importlib.util
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("an", f"{HERE}/06_analyze.py")
an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)
bt = an.bt; D = bt.D
OUT = f"{HERE}/dev_results"; os.makedirs(OUT, exist_ok=True)


# ---------------- event-level text features (from 08_jev_score.py output) ----------------
def event_text_feats():
    mem = pd.read_parquet(f"{D}/event_members_v2.parquet")
    p = pd.read_parquet(f"{D}/purchases_v2.parquet", columns=["owner_cik"])
    j = pd.read_parquet(f"{D}/jev_purchase_v2.parquet")
    x = mem.join(p, on="pid").join(j, on="pid")
    aff = x.aff10b5one.astype(str).str.lower().isin(["1", "true"])
    x["nd_jev"] = ((x.src_offering + x.src_private_placement + x.src_plan) >= 0.5) | (x.p10b5 >= 0.5) | aff
    x["nd_kw"] = (x.kw_offering + x.kw_private + x.kw_plan + x.kw_10b5 > 0) | aff
    x["ind_jev"] = x.pind >= 0.5; x["rng_jev"] = x.prange >= 0.5
    x["ind_kw"] = x.kw_indirect > 0; x["rng_kw"] = x.kw_range > 0
    x["off_jev"] = x.src_offering >= 0.5; x["pp_jev"] = x.src_private_placement >= 0.5
    x["plan_jev"] = x.src_plan >= 0.5; x["b10_jev"] = x.p10b5 >= 0.5
    x["clean_jev"] = ~x.nd_jev; x["clean_kw"] = ~x.nd_kw
    ins = x.groupby(["ev", "owner_cik"]).agg(
        clean_jev=("clean_jev", "max"), clean_kw=("clean_kw", "max"), ind_jev=("ind_jev", "max"),
        rng_jev=("rng_jev", "max"), ind_kw=("ind_kw", "max"), rng_kw=("rng_kw", "max"),
        off_jev=("off_jev", "max"), pp_jev=("pp_jev", "max"), plan_jev=("plan_jev", "max"), b10_jev=("b10_jev", "max"),
        lm_neg=("lm_neg", "sum"), lm_pos=("lm_pos", "sum"), lm_unc=("lm_unc", "sum"), has_text=("has_text", "max"))
    e = ins.groupby("ev").agg(
        n_clean_jev=("clean_jev", "sum"), n_clean_kw=("clean_kw", "sum"),
        f_ind_jev=("ind_jev", "mean"), f_rng_jev=("rng_jev", "mean"), f_ind_kw=("ind_kw", "mean"),
        f_rng_kw=("rng_kw", "mean"), f_off_jev=("off_jev", "mean"), f_pp_jev=("pp_jev", "mean"),
        f_plan_jev=("plan_jev", "mean"), f_b10_jev=("b10_jev", "mean"),
        lm_neg=("lm_neg", "mean"), lm_pos=("lm_pos", "mean"), lm_unc=("lm_unc", "mean"), f_text=("has_text", "mean"))
    return e


def load():
    ev, paths, bench = an.get_prepared()
    ev = ev.join(event_text_feats())
    return ev, paths, bench


# ---------------- extra filters (SEC-text based => also applied to the no-price names) ----------------
an.SEC_FILTERS.update({
    "B:jev_clean>=3": lambda e: e.n_clean_jev >= 3,
    "dict:kw_clean>=3": lambda e: e.n_clean_kw >= 3,
    "B:jev_clean>=3 & opp": lambda e: (e.n_clean_jev >= 3) & (e.n_opp >= 3),
    "dict:kw_clean>=3 & opp": lambda e: (e.n_clean_kw >= 3) & (e.n_opp >= 3),
    "B:jev_clean>=3 & no_indirect_majority": lambda e: (e.n_clean_jev >= 3) & (e.f_ind_jev < 0.5),
    "B:jev_clean>=3 & range>=1/3": lambda e: (e.n_clean_jev >= 3) & (e.f_rng_jev >= 1 / 3),
    "B:jev_nonclean(any offering/pp/plan/10b5-1)": lambda e: e.n_clean_jev < e.n_ins,
})
BASE_ONLY_H = (21, 63, 126, 252)


def rules(ev, paths, bench):
    per = (ev.fdate >= "2006-01-01") & (ev.fdate <= "2015-12-31")
    endH = lambda H: bench.index[min(len(bench) - 1, int(ev[per & (ev.status == "ok")].ent_ci.max()) + H)]
    rows = []
    names_A = ["base", "opportunistic(n_opp>=3)", "big_buys(med pct_hold>=10%)", "ceo_or_cfo_in_cluster",
               "after_decline(ret63<0)", "all4(opp+big+ceo/cfo+decline)", "n_ins>=4", "n_ins>=5"]
    names_B = [k for k in an.SEC_FILTERS if k.startswith(("B:", "dict:"))]
    for name in names_A + names_B:
        for H in (BASE_ONLY_H if name in ("base", "opportunistic(n_opp>=3)", "B:jev_clean>=3") else (126,)):
            r, eq = an.run_variant(ev, paths, bench, per, name, H=H, start="2006-01-01", end=endH(H))
            sel = ev[per & an.base_mask(ev) & an.variant_mask(ev, name)]
            xi, xs = an.event_excess(sel, bench, H)
            r["ev_ex_iwm_mean"] = float(np.nanmean(xi)); r["ev_ex_iwm_med"] = float(np.nanmedian(xi))
            r["ev_ex_iwm_t"] = float(np.nanmean(xi) / (np.nanstd(xi) / np.sqrt(np.isfinite(xi).sum())))
            r["cap_10pctADV_$M"] = float(np.median(0.1 * sel.adv) * r["avg_pos"] / 1e6)
            rows.append(r)
            print(an.fmt(pd.DataFrame([r])).drop(columns=["window"]).to_string(index=False), flush=True)
            pd.DataFrame(rows).to_csv(f"{OUT}/rules_raw.csv", index=False)
    res = an.fmt(pd.DataFrame(rows)); res.to_csv(f"{OUT}/rules.csv", index=False)
    # halves for the main candidates
    rows = []
    for lab, a, b in [("2006-2010", "2006-01-01", "2010-12-31"), ("2011-2015", "2011-01-01", "2015-12-31")]:
        ph = (ev.fdate >= a) & (ev.fdate <= b)
        eH = bench.index[min(len(bench) - 1, int(ev[ph & (ev.status == 'ok')].ent_ci.max()) + 126)]
        for name in names_A + names_B:
            r, _ = an.run_variant(ev, paths, bench, ph, name, H=126, start=a, end=eH, top_cut=False)
            r["half"] = lab; rows.append(r)
    hv = an.fmt(pd.DataFrame(rows)); hv.to_csv(f"{OUT}/rules_halves.csv", index=False)
    print(hv[["half", "variant", "n_events", "cagr", "cagr_2x", "cagr_miss-50", "spy", "iwm"]].to_string(index=False))


# ---------------- ML comparison ----------------
FA = ["l_nins", "opp_frac", "l_pct", "has_ceo_cfo", "ret63", "ret126", "l_dollars", "l_adv", "l_price", "vol_d", "off_frac"]
FJ = ["clean_frac_jev", "f_ind_jev", "f_rng_jev", "f_off_jev", "f_pp_jev", "f_plan_jev", "f_b10_jev"]
FK = ["clean_frac_kw", "f_ind_kw", "f_rng_kw", "lm_neg", "lm_pos", "lm_unc"]


def ml_frame(ev, bench, H=126):
    e = ev[an.base_mask(ev)].copy()
    e["l_nins"] = np.log(e.n_ins); e["opp_frac"] = e.n_opp / e.n_ins; e["off_frac"] = e.n_off / e.n_ins
    e["l_pct"] = np.log1p(e.med_pct_hold); e["l_dollars"] = np.log1p(e.dollars); e["l_adv"] = np.log(e.adv)
    e["l_price"] = np.log(e.price); e["has_ceo_cfo"] = e.has_ceo_cfo.astype(float)
    e["clean_frac_jev"] = e.n_clean_jev / e.n_ins; e["clean_frac_kw"] = e.n_clean_kw / e.n_ins
    xi, _ = an.event_excess(e, bench, H)
    e["y_ex"] = xi; e["y"] = (xi > 0).astype(int)
    e[FA + FJ + FK] = e[FA + FJ + FK].astype(float).fillna(0)
    return e


def fit_predict(tr, te, feats):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    trc = tr.copy(); trc[feats] = trc[feats].clip(tr[feats].quantile(0.01), tr[feats].quantile(0.99), axis=1)
    tec = te.copy(); tec[feats] = tec[feats].clip(tr[feats].quantile(0.01), tr[feats].quantile(0.99), axis=1)
    m.fit(trc[feats], trc.y)
    return m.predict_proba(tec[feats])[:, 1], m.predict_proba(trc[feats])[:, 1]


def ml(ev, paths, bench, H=126):
    from sklearn.metrics import roc_auc_score
    e = ml_frame(ev, bench, H)
    dev = e[(e.fdate >= "2006-01-01") & (e.fdate <= "2015-12-31") & e.y_ex.notna()]
    # train only on events whose exit is before the prediction year starts (no overlap leakage)
    rows, sel = [], {k: [] for k in ("A", "A+Jev", "A+dict")}
    for y in range(2009, 2016):
        cut = pd.Timestamp(f"{y}-01-01")
        exit_date = bench.index[np.minimum(dev.ent_ci.astype(int) + H, len(bench) - 1)]
        tr = dev[(exit_date < cut)]; te = dev[dev.fdate.dt.year == y]
        for k, f in (("A", FA), ("A+Jev", FA + FJ), ("A+dict", FA + FK)):
            s, s_tr = fit_predict(tr, te, f)
            thr = np.quantile(s_tr, 2 / 3)
            top = te[s >= thr]
            sel[k] += list(top.index)
            rows.append(dict(year=y, model=k, n_tr=len(tr), n_te=len(te), auc=roc_auc_score(te.y, s),
                             top_n=len(top), top_ex=top.y_ex.mean(), all_ex=te.y_ex.mean()))
    r = pd.DataFrame(rows); r.to_csv(f"{OUT}/ml_walkforward.csv", index=False)
    print(r.groupby("model")[["auc", "top_ex", "all_ex"]].mean().round(4).to_string())
    # portfolio of walk-forward top-tercile picks, 2009-2015 entries (identical dates across models)
    per = (ev.fdate >= "2009-01-01") & (ev.fdate <= "2015-12-31")
    eH = bench.index[min(len(bench) - 1, int(ev[per & (ev.status == "ok")].ent_ci.max()) + H)]
    out = []
    for k, idx in sel.items():
        s = ev.loc[idx]
        eq, nact = bt.simulate(s, paths, bench, H=H, start="2009-01-01", end=eH)
        eq2, _ = bt.simulate(s, paths, bench, H=H, start="2009-01-01", end=eH, cost_mult=2)
        out.append(dict(model=k, n=len(s), cagr=bt.cagr(eq), cagr_2x=bt.cagr(eq2), maxdd=bt.maxdd(eq),
                        spy=bt.bench_cagr(bench, eq.index[0], eq.index[-1], "SPY"),
                        iwm=bt.bench_cagr(bench, eq.index[0], eq.index[-1], "IWM")))
    s = ev[per & an.base_mask(ev)]
    eq, _ = bt.simulate(s, paths, bench, H=H, start="2009-01-01", end=eH)
    out.append(dict(model="all(base)", n=len(s), cagr=bt.cagr(eq), maxdd=bt.maxdd(eq)))
    o = pd.DataFrame(out); o.to_csv(f"{OUT}/ml_portfolios.csv", index=False)
    print(o.round(4).to_string(index=False))
    # full-DEV coefficients (for the record)
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    Z = StandardScaler().fit_transform(dev[FA + FJ].clip(dev[FA + FJ].quantile(0.01), dev[FA + FJ].quantile(0.99), axis=1))
    c = LogisticRegression(C=0.1, max_iter=2000).fit(Z, dev.y).coef_[0]
    pd.Series(c, FA + FJ).round(3).to_csv(f"{OUT}/ml_coefs_A+Jev.csv")
    print(pd.Series(c, FA + FJ).round(3).to_string())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "prep":
        ev, paths, bench = an.get_prepared(); print(ev.status.value_counts()); sys.exit()
    ev, paths, bench = load()
    per = (ev.fdate >= "2006-01-01") & (ev.fdate <= "2015-12-31")
    if mode in ("rules", "all"):
        evp = ev[per]
        cov = pd.crosstab(evp.fdate.dt.year, evp.status, margins=True)
        cov["frac_ok"] = (cov.get("ok", 0) / cov["All"]).round(3); cov.to_csv(f"{OUT}/coverage.csv")
        print(cov.to_string())
        el = evp[evp.vwap >= 2]
        print("DEV events vwap>=$2:", len(el), "no usable price:", round((el.status != "ok").mean(), 3))
        print("Jev/dict text features (DEV events):")
        print(evp[["n_ins", "n_clean_jev", "n_clean_kw", "f_ind_jev", "f_rng_jev", "f_off_jev", "f_pp_jev",
                   "f_plan_jev", "f_b10_jev", "f_text"]].describe().round(3).to_string())
        rules(ev, paths, bench)
    if mode in ("ml", "all"):
        ml(ev, paths, bench)
