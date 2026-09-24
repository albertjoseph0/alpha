"""Full report tables for one period/config: costs 1x/2x, survivorship scenarios, trend switch,
K sensitivity, controls, rank IC (model vs 12-1 momentum, paired t), permutation importances,
factor tilts, capacity. usage: s06_report.py dev|test <config>"""
import sys
from s05_model import *

period, name = sys.argv[1], sys.argv[2]
lo, hi = DEV if period == "dev" else TEST
S = pd.read_parquet(DATA / f"scores_{period}_{name}.parquet")
P, months = load()
lines = []


def pr(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    lines.append(s)


def row(r, spy, label):
    s = summ(r, spy, label)
    return f"| {label} | {s['cagr']*100:.1f}% | {s['excess']*100:+.1f} | {s['maxdd']*100:.1f}% | {s['vol']*100:.1f}% | {s['sharpe_ish']:.2f} |"


pr(f"# {period.upper()} report: {name} (holding months {S.form.min().date()}+1m .. {S.form.max().date()}+1m)\n")
pr("| variant | CAGR | vs SPY (pts) | maxDD | vol | Sharpe(0rf) |")
pr("|---|---|---|---|---|---|")
base = backtest(S, "score")
spy = base["spy"]
pr(row(spy, spy, "SPY (buy & hold)"))
for cm in (1.0, 2.0):
    ew = backtest(S, "__ew__", cost_mult=cm)
    pr(row(ew["net"], spy, f"EW universe, {cm:g}x cost"))
    mo = backtest(S, "mom12_1", cost_mult=cm)
    pr(row(mo["net"], spy, f"ctrl 12-1 momentum top{K}, {cm:g}x cost"))
    b = backtest(S, "score", cost_mult=cm)
    pr(row(b["net"], spy, f"MODEL top{K}, {cm:g}x cost"))
    b.to_csv(OUT / f"bt_{period}_{name}_x{cm:g}.csv")
    ts, u = trend_overlay(b, cm)
    pr(row(ts, spy, f"MODEL top{K} + SPY trend switch, {cm:g}x cost"))
    tm, _ = trend_overlay(mo, cm)
    pr(row(tm, spy, f"ctrl momentum + trend switch, {cm:g}x cost"))
    pd.DataFrame({"model": b["net"], "model_switch": ts, "mom": mo["net"], "mom_switch": tm,
                  "ew": ew["net"], "spy": spy, "trend_u": u}).to_csv(OUT / f"monthly_{period}_{name}_x{cm:g}.csv")
pr("\nSurvivorship / missing-price scenarios (model top25, 1x cost):\n")
pr("| scenario | CAGR | vs SPY | maxDD | vol | Sharpe |")
pr("|---|---|---|---|---|---|")
for scen in ("drop", "neutral", "x50", "x100"):
    for ended in ("last", "m50", "m100"):
        if scen != "drop" and ended != "last" and not (scen == "x100" and ended == "m100"):
            continue
        b = backtest(S, "score", scen=scen, ended=ended)
        pr(row(b["net"], spy, f"missing={scen}, series-ends-in-hold={ended}"))
        if scen == "x100" and ended == "m100":
            e2 = backtest(S, "__ew__", scen=scen, ended=ended)
            pr(row(e2["net"], spy, "EW universe under the same worst case"))
            m2 = backtest(S, "mom12_1", scen=scen, ended=ended)
            pr(row(m2["net"], spy, "momentum under the same worst case"))
pr("\nK sensitivity (1x cost, reported only; K=25 frozen):\n")
pr("| K | CAGR | vs SPY | maxDD | vol | Sharpe |")
pr("|---|---|---|---|---|---|")
for k in (10, 20, 25, 30, 50, 100):
    b = backtest(S, "score", k=k)
    pr(row(b["net"], spy, f"K={k}"))

# yearly
b1 = backtest(S, "score")
mo = backtest(S, "mom12_1")
ew = backtest(S, "__ew__")
Y = pd.DataFrame({"model": b1["net"], "mom": mo["net"], "ew": ew["net"], "spy": spy})
Y.index = (pd.to_datetime(b1["form"]) + pd.offsets.MonthEnd(1)).values
Y = (1 + Y).groupby(Y.index.year).prod() - 1
Y.index.name = "year"
pr("\nCalendar-year net returns (1x cost):\n")
pr(md((Y * 100).round(1)))

# rank IC
ic_m = rank_ic(S, "score")
ic_mo = rank_ic(S, "mom12_1")
d = (ic_m - ic_mo).dropna()
pr("\nMonthly rank IC (Spearman, score vs next-month return, eligible universe):\n")
pr("| signal | mean IC | t-stat | % months > 0 | months |")
pr("|---|---|---|---|---|")
for lab, ic in (("model score", ic_m), ("12-1 momentum", ic_mo)):
    st = ic_stats(ic)
    pr(f"| {lab} | {st['mean']:.4f} | {st['t']:.2f} | {st['hit']*100:.0f}% | {st['n']} |")
pr(f"| model minus momentum (paired) | {d.mean():.4f} | {d.mean()/d.std()*np.sqrt(len(d)):.2f} | {(d>0).mean()*100:.0f}% | {len(d)} |")
# top-minus-universe spread
spread = (b1["gross"] - ew["gross"])
pr(f"\nTop{K} gross minus EW-universe gross: mean {spread.mean()*100:.2f}%/month, t {spread.mean()/spread.std()*np.sqrt(len(spread)):.2f}")

# turnover, trades, capacity
pr(f"\nAvg one-way turnover/month (model): {b1['turnover'].mean()/2*100:.0f}% ; momentum: {mo['turnover'].mean()/2*100:.0f}%")
nbuys = 0
prev = set()
for h in b1["hold"]:
    cur = set(h.split(","))
    nbuys += len(cur - prev)
    prev = cur
pr(f"Distinct position entries (trades in): {nbuys} over {len(b1)} months; avg cost drag {b1['cost'].mean()*12*100:.2f}%/yr at 1x")
P2 = P.set_index(["form", "ticker"])
dvs = []
for (f, h) in zip(b1["form"], b1["hold"]):
    dv = np.exp(P2.loc[[(f, t) for t in h.split(",")], "size_dv"]) - 1
    dvs.append(dv.min())
dvs = pd.Series(dvs)
pr(f"Least-liquid holding's median daily $ volume: median ${dvs.median()/1e6:.0f}M (10th pct month ${dvs.quantile(0.1)/1e6:.0f}M)."
   f" At 5% of ADV per name per rebalance day -> capacity ~ {K} x 5% x ${dvs.quantile(0.1)/1e6:.0f}M = ${K*0.05*dvs.quantile(0.1)/1e6:.0f}M per day of trading")
pr(f"Share of S&P 500 names in model book: {b1['frac500'].mean()*100:.0f}%")

# tilts: average cross-sectional percentile of holdings on each feature
tilt = []
for (f, h) in zip(b1["form"], b1["hold"]):
    g = P[P.form == f].set_index("ticker")
    rk = g[FEATS].rank(pct=True)
    tilt.append(rk.loc[h.split(",")].mean())
tilt = pd.DataFrame(tilt).mean()
pr("\nAverage cross-sectional percentile of model holdings per feature (0.5 = neutral):\n")
pr(md(tilt.round(2).to_frame("pctile").T))

# permutation importance (IC drop when a feature is shuffled within month), refitting the walk-forward
cfg = CONFIGS[name]
xc = [f"x_{c}" for c in FEATS]
rng = np.random.default_rng(0)
forms = sorted(P.loc[(P.form >= lo) & (P.form <= hi), "form"].unique())
drops = {c: [] for c in FEATS}
base_ic = []
model, yr_tr = None, None
for f in forms:
    f = pd.Timestamp(f)
    yr = f.year + (1 if f.month == 12 else 0)
    if model is None or yr != yr_tr:
        tr = P[(P.t1 <= f) & P.y.notna()]
        Xt = tr[xc].values if cfg["kind"] == "hgb" else np.nan_to_num(tr[xc].values)
        model = make_model(cfg).fit(Xt, tr.y.values)
        yr_tr = yr
        if cfg["kind"] == "rf":
            imp_rf = pd.Series(model.feature_importances_, index=FEATS)
    te = P[(P.form == f) & P.ret.notna()]
    Xe = te[xc].values.copy()
    if cfg["kind"] != "hgb":
        Xe = np.nan_to_num(Xe)
    b0 = pd.Series(model.predict(Xe)).corr(te["ret"].reset_index(drop=True), method="spearman")
    base_ic.append(b0)
    for j, c in enumerate(FEATS):
        X2 = Xe.copy()
        X2[:, j] = rng.permutation(X2[:, j])
        drops[c].append(b0 - pd.Series(model.predict(X2)).corr(te["ret"].reset_index(drop=True), method="spearman"))
imp = pd.DataFrame({"ic_drop_mean": {c: np.mean(v) for c, v in drops.items()},
                    "t": {c: np.mean(v) / (np.std(v) + 1e-12) * np.sqrt(len(v)) for c, v in drops.items()}})
imp = imp.sort_values("ic_drop_mean", ascending=False)
imp.to_csv(OUT / f"importance_{period}_{name}.csv")
pr("\nPermutation importance (mean drop in monthly rank IC when the feature is shuffled; positive = the model uses it and it helps OOS):\n")
pr(md(imp.round(4)))
# single-feature ICs for reference
pr("\nSingle-feature monthly rank ICs (raw feature vs next-month return):\n")
fi = []
for c in FEATS:
    ic = P[(P.form >= lo) & (P.form <= hi)].groupby("form").apply(lambda g: g[c].corr(g["ret"], method="spearman"))
    st = ic_stats(ic)
    fi.append((c, st["mean"], st["t"]))
pr(md(pd.DataFrame(fi, columns=["feature", "mean_ic", "t"]).set_index("feature").round(4)))
open(OUT / f"report_{period}_{name}.md", "w").write("\n".join(lines) + "\n")
