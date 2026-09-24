"""Round 5b: frozen rules from PREREG.md evaluated on DEV (2006-2015, for reference) and on the sealed
TEST period (events FILED 2016-01-01 .. 2026q1). Run ONCE after PREREG.md is written.
usage: python 09_test.py [dev|test]   (dev = same code on DEV only, allowed before the prereg run)
Output: test_results/frozen_{dev,test}.csv, test_results/ml_{dev,test}.csv
"""
import sys, os, importlib.util
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("dv", f"{HERE}/07_dev.py")
dv = importlib.util.module_from_spec(spec); spec.loader.exec_module(dv)
an, bt = dv.an, dv.bt
OUT = f"{HERE}/test_results"; os.makedirs(OUT, exist_ok=True)

H = 126                                               # frozen (PREREG.md)
FROZEN = {"A": "opportunistic(n_opp>=3)",              # frozen (PREREG.md)
          "A+B": "B:jev_clean>=3 & opp",
          "ref:base": "base", "ref:dict": "dict:kw_clean>=3 & opp"}


def period(ev, which):
    if which == "dev":
        return (ev.fdate >= "2006-01-01") & (ev.fdate <= "2015-12-31"), "2006-01-01"
    return ev.fdate >= "2016-01-01", "2016-01-01"


def frozen_rules(ev, paths, bench, which):
    per, start = period(ev, which)
    end = bench.index[min(len(bench) - 1, int(ev[per & (ev.status == "ok")].ent_ci.max()) + H)]
    rows = []
    for lab, name in FROZEN.items():
        r, eq = an.run_variant(ev, paths, bench, per, name, H=H, start=start, end=end)
        sel = ev[per & an.base_mask(ev) & an.variant_mask(ev, name)]
        miss = an.missing_set(ev, per, name)
        r["cagr_miss0"] = bt.cagr(bt.simulate(sel, paths, bench, H=H, start=start, end=end,
                                              missing=miss, missing_ret=0.0)[0])
        xi, xs = an.event_excess(sel, bench, H)
        r.update(label=lab, ev_ex_iwm_mean=float(np.nanmean(xi)), ev_ex_iwm_med=float(np.nanmedian(xi)),
                 ev_ex_iwm_t=float(np.nanmean(xi) / (np.nanstd(xi) / np.sqrt(np.isfinite(xi).sum()))),
                 ev_ex_spy_mean=float(np.nanmean(xs)), mean_cost=float(sel.cost.mean()),
                 cap_10pctADV_M=float(np.median(0.1 * sel.adv) * r["avg_pos"] / 1e6))
        rows.append(r); eq.to_csv(f"{OUT}/equity_{which}_{lab.replace(':', '_')}.csv")
        print(an.fmt(pd.DataFrame([r])).to_string(index=False), flush=True)
    res = an.fmt(pd.DataFrame(rows)); res.to_csv(f"{OUT}/frozen_{which}.csv", index=False)
    return res


def ml_frozen(ev, paths, bench, which):
    """logistic regression trained on ALL DEV events whose exit precedes 2016-01-01; buy the top tercile
    (threshold = 2/3 quantile of in-sample DEV scores). Same model with A features, A+Jev, A+dict."""
    e = dv.ml_frame(ev, bench, H)
    exit_date = bench.index[np.minimum(e.ent_ci.astype(int) + H, len(bench) - 1)]
    tr = e[(e.fdate >= "2006-01-01") & (exit_date < pd.Timestamp("2016-01-01")) & e.y_ex.notna()]
    per, start = period(ev, which)
    te = e[per.reindex(e.index).fillna(False)]
    te = te[te.y_ex.notna()]
    end = bench.index[min(len(bench) - 1, int(te.ent_ci.max()) + H)]
    from sklearn.metrics import roc_auc_score
    rows = []
    for k, f in (("A", dv.FA), ("A+Jev", dv.FA + dv.FJ), ("A+dict", dv.FA + dv.FK)):
        s, s_tr = dv.fit_predict(tr, te, f)
        top = te[s >= np.quantile(s_tr, 2 / 3)]
        eq, _ = bt.simulate(ev.loc[top.index], paths, bench, H=H, start=start, end=end)
        eq2, _ = bt.simulate(ev.loc[top.index], paths, bench, H=H, start=start, end=end, cost_mult=2)
        rows.append(dict(model=k, n=len(top), auc=roc_auc_score(te.y, s), top_ex_iwm=top.y_ex.mean(),
                         all_ex_iwm=te.y_ex.mean(), cagr=bt.cagr(eq), cagr_2x=bt.cagr(eq2), maxdd=bt.maxdd(eq),
                         spy=bt.bench_cagr(bench, eq.index[0], eq.index[-1], "SPY"),
                         iwm=bt.bench_cagr(bench, eq.index[0], eq.index[-1], "IWM")))
    r = pd.DataFrame(rows); r.to_csv(f"{OUT}/ml_{which}.csv", index=False)
    print(r.round(4).to_string(index=False))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    ev, paths, bench = dv.load()
    per, _ = period(ev, which)
    evp = ev[per]
    cov = pd.crosstab(evp.fdate.dt.year, evp.status, margins=True)
    cov["frac_ok"] = (cov.get("ok", 0) / cov["All"]).round(3); cov.to_csv(f"{OUT}/coverage_{which}.csv")
    print(cov.to_string())
    frozen_rules(ev, paths, bench, which)
    ml_frozen(ev, paths, bench, which)
