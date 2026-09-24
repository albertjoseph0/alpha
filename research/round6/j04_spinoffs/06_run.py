"""Step 6: run the pre-specified filters on one period.
  06_run.py dev            -> results_dev.json / results_dev.csv (+ N/M grid, ablations, survivorship bounds)
  06_run.py test --sealed  -> results_test.* (only after PREREG.md exists; run once)
Filters (identical events and dates; nested information sets):
  A_all    : every exchange-listed spin-off with prices                         (a) no text
  A_small  : size mismatch f < 0.20 (spin-off value / pre-spin parent value)    (a) no text
  B_kw     : >=2 of {kw_grants, kw_debt_to_parent, sic_diff, small}             (b) keyword rules
  C_jev    : >=2 of {jev_mgmt_grants>.5, jev_debt_to_parent>.5, jev_diff_industry>.5, small}  (c) Jev
"""
import importlib.util, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bt", f"{HERE}/05_backtest.py")
bt = importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)
D = bt.D
period = sys.argv[1]
if period == "test":
    assert os.path.exists(f"{HERE}/PREREG.md") and "--sealed" in sys.argv, "write PREREG.md first"
N0, M0 = 20, 12          # primary entry delay (trading days) and holding period (months), fixed a priori
F_SMALL = 0.20

ev = pd.read_csv(f"{D}/events.csv", parse_dates=["first_trade"])
ev["period_date"] = ev.first_trade.fillna(pd.to_datetime(ev.doc_date) + pd.Timedelta(days=21))
lo, hi = ("2004-01-01", "2015-01-01") if period == "dev" else ("2015-01-01", "2100-01-01")
ev = ev[(ev.period_date >= lo) & (ev.period_date < hi)]
kw = pd.read_csv(f"{D}/features_kw_{period}.csv")
jv = pd.read_csv(f"{D}/features_jev_{period}.csv")
ev = ev.merge(kw, on="cik", how="left").merge(jv, on="cik", how="left")
ev["small"] = (ev.f_size < F_SMALL).astype(int)
ev["sic_diff"] = ((ev.sic.fillna(-1) // 100 != ev.parent_sic.fillna(-2) // 100) & ev.parent_sic.notna() & ev.sic.notna()).astype(int)
ev["B_score"] = ev[["kw_grants", "kw_debt_to_parent", "sic_diff", "small"]].fillna(0).sum(axis=1)
for q in ["mgmt_grants", "debt_to_parent", "diff_industry", "parent_stake", "pays_dividend"]:
    ev[f"J_{q}"] = (ev[f"jev_{q}"] > 0.5).astype(int)
ev["C_score"] = ev[["J_mgmt_grants", "J_debt_to_parent", "J_diff_industry", "small"]].sum(axis=1)
ev.to_csv(f"{D}/panel_{period}.csv", index=False)

priced = ev[ev.yf_ticker.notna()].copy()
unpriced = ev[ev.yf_ticker.isna() & ev.completed.fillna(False).astype(bool)].copy()
B = {t: bt.bench(t) for t in ["SPY", "IWM", "IJH"]}

FILTERS = {
    "A_all": lambda d: d,
    "A_small": lambda d: d[d.small == 1],
    "B_kw": lambda d: d[d.B_score >= 2],
    "C_jev": lambda d: d[d.C_score >= 2],
}

paths, info = bt.event_paths(priced, N0, M0)
window = (info.entry.min(), info.exit.max())
rows = []
for cm in (1.0, 2.0):
    for name, f in FILTERS.items():
        r = bt.summarize(name, f(priced), paths, info, B, cm, window)
        r["cost_mult"] = cm
        rows.append(r)
res = pd.DataFrame(rows)
print(res.round(3).to_string())

# bootstrap CAGR-excess CI (events resampled) for primary filters at 1x costs
boots = {name: list(bt.boot_cagr(f(priced), paths, info, B, 300)) for name, f in FILTERS.items()}
print("bootstrap CAGR-SPY [2.5,50,97.5]:", {k: np.round(v, 3).tolist() for k, v in boots.items()})

extra = {}
if period == "dev":
    # N/M grid for A_all and C_jev (reported in full; primary stays N0/M0)
    grid = []
    for N in (1, 5, 20, 60):
        for M in (6, 12, 24):
            p2, i2 = bt.event_paths(priced, N, M)
            for name in ("A_all", "B_kw", "C_jev"):
                r = bt.summarize(name, FILTERS[name](priced), p2, i2, B, 1.0)
                grid.append(dict(N=N, M=M, filter=name, n=r["n"], ex_SPY=r.get("ex_SPY"), mean_bhar_spy=r.get("mean_bhar_spy")))
    grid = pd.DataFrame(grid)
    grid.to_csv(f"{HERE}/grid_dev.csv", index=False)
    print(grid.pivot_table(index=["N", "M"], columns="filter", values="ex_SPY").round(3))

# single-feature ablations (event-level mean BHAR vs SPY, in/out)
abl = []
ex_all = info.set_index("cik").ret - pd.Series(bt.bhar(info, B["SPY"]), index=info.cik)
for col in ["small", "kw_grants", "kw_debt_to_parent", "sic_diff", "kw_parent_stake", "kw_pays_dividend",
            "J_mgmt_grants", "J_debt_to_parent", "J_diff_industry", "J_parent_stake", "J_pays_dividend"]:
    s = priced.set_index("cik")[col].reindex(ex_all.index)
    abl.append(dict(feature=col, n_yes=int((s == 1).sum()), bhar_yes=ex_all[s == 1].mean(), bhar_no=ex_all[s == 0].mean()))
for c in ["strategic_focus", "activist_pressure", "regulatory", "tax", "separate_underperforming_unit"]:
    s = priced.set_index("cik")["jev_reason"].reindex(ex_all.index) == c
    abl.append(dict(feature=f"reason={c}", n_yes=int(s.sum()), bhar_yes=ex_all[s].mean(), bhar_no=ex_all[~s].mean()))
abl = pd.DataFrame(abl)
print(abl.round(3).to_string())

# survivorship: completed spin-offs without usable prices
surv = []
n_tot = len(priced) + len(unpriced)
for name, f in FILTERS.items():
    sel_p, sel_u = f(priced), f(unpriced.assign(small=0))
    if name == "A_small":
        sel_u = unpriced.iloc[0:0]  # f unknown without prices
    base = bt.summarize(name, sel_p, paths, info, B, 1.0, window)
    med = info[info.cik.isin(sel_p.cik)].ret.median()
    for scen, fn in {"-100%": lambda r: -0.999, "-50%": lambda r: -0.5,
                     "fate": lambda r: -0.999 if r.bankrupt else (med if r.merger_filings else -0.5)}.items():
        p3, i3 = dict(paths), info.copy()
        add = []
        for _, r in sel_u.iterrows():
            ent = pd.Timestamp(r.period_date) + pd.tseries.offsets.BDay(N0)
            ex = ent + pd.DateOffset(months=M0)
            idx = B["SPY"].index[(B["SPY"].index >= ent) & (B["SPY"].index <= ex)]
            if len(idx) < 2:
                continue
            tot = fn(r)
            dr = (1 + tot) ** (1 / len(idx)) - 1
            key = f"u{r.cik}"
            p3[key] = pd.Series(dr, index=idx)
            add.append(dict(cik=key, entry=idx[0], exit=idx[-1], planned_exit=ex, truncated=False, ret=tot, cost_bp=60.0))
        i3 = pd.concat([i3, pd.DataFrame(add)], ignore_index=True)
        sel = pd.concat([sel_p[["cik"]], pd.DataFrame({"cik": [a["cik"] for a in add]})])
        r2 = bt.summarize(name, sel, p3, i3, B, 1.0, window)
        surv.append(dict(filter=name, scenario=scen, n_priced=len(sel_p), n_unpriced=len(add), ex_SPY=r2.get("ex_SPY"),
                         base_ex_SPY=base.get("ex_SPY")))
surv = pd.DataFrame(surv)
print(surv.round(3).to_string())

missing = dict(n_listed_completed=int(n_tot), n_priced=int(len(priced)), n_unpriced=int(len(unpriced)),
               frac_missing=float(len(unpriced) / max(n_tot, 1)),
               unpriced_merger=int(unpriced.merger_filings.fillna(False).astype(bool).sum()),
               unpriced_bankrupt=int(unpriced.bankrupt.fillna(False).astype(bool).sum()))
print(missing)
res.to_csv(f"{HERE}/results_{period}.csv", index=False)
abl.to_csv(f"{HERE}/ablation_{period}.csv", index=False)
surv.to_csv(f"{HERE}/survivorship_{period}.csv", index=False)
json.dump(dict(boot=boots, missing=missing, window=[str(window[0].date()), str(window[1].date())]),
          open(f"{HERE}/results_{period}.json", "w"), indent=1)
info.merge(priced[["cik", "name", "yf_ticker", "B_score", "C_score", "small", "f_size", "mcap0"]], on="cik").to_csv(
    f"{D}/trades_{period}.csv", index=False)
