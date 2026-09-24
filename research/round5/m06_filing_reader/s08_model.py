"""Models + monthly portfolio for m06 (filing reader).
MODE=dev : filings 2020-01..2022-12, purged leave-one-year-out CV (out-of-fold scores), prices truncated
           at 2022-12-30 so nothing from the sealed test period is read.
MODE=test: final models fit on all dev events (labels ending <= 2022-12-30), applied to 2023-01.. events.
Usage: s08_model.py dev|test [full|jev]
  full: price / +LM / +FinBERT on every event.  jev: identical-events comparison of price / +LM / +FinBERT / +Jev
  restricted to Jev-scored events (DEV 2020-01..2021-06 with half-year folds; TEST 2023 filings, first rebalance
  2023-01, last rebalance the month after Jev coverage ends).
Outputs (research folder): results_<mode>_<sub>.csv (portfolio stats), ic_<mode>_<sub>.csv; monthly_*.parquet in DATA."""
import sys, warnings
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from common import DATA, RES
warnings.filterwarnings("ignore")

MODE = sys.argv[1]
SUB = sys.argv[2] if len(sys.argv) > 2 else "full"
assert MODE in ("dev", "test") and SUB in ("full", "jev")
DEV_START, DEV_END = pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")
DEV_PX_END = pd.Timestamp("2022-12-30")
TEST_START = pd.Timestamp("2023-01-01")
# ---------------- frozen settings ----------------
H = 63                    # label horizon (trading days from entry open): ~3 months
TOPN = 40                 # names held
LOOKBACK = 63             # eligible: entry within the last 63 trading days (latest release per firm)
COST_BP = 10.0            # per side; also reported at 2x (20bp) and 0
PRIMARY = "logit"         # primary model; "gbt" reported as secondary
PRICE = ["gap_x", "day0_x", "mom_12_1", "mom_1m", "vol60"]
DICT = ["lm_tone", "lm_pos", "lm_neg", "lm_tone_chg", "lm_pos_chg", "lm_neg_chg", "has_prev"]
FB = ["fb_mean", "fb_head", "fb_neg", "fb_frac_neg", "fb_mean_chg", "fb_head_chg", "fb_neg_chg", "has_prev"]
# -------------------------------------------------

E = pd.read_parquet(DATA / "events_scored.parquet")
JEV = sorted(c for c in E.columns if c.startswith("j_")) + ["jev_has_prev"]
PREV_Q = ("j_guid_spec_vs_prev", "j_caution_vs_prev", "j_tone_vs_prev")
for c in [c for c in JEV if c.startswith(PREV_Q)]:
    E.loc[E.jev_has_prev != 1, c] = np.nan      # comparison answers only meaningful with a previous release
FB_NP = [f for f in FB if f != "has_prev"]
if SUB == "full":
    SETS = {"price": PRICE, "price+dict": PRICE + DICT, "price+finbert": PRICE + FB, "price+dict+finbert": PRICE + DICT + FB_NP,
            "dict_only": DICT, "finbert_only": FB}
else:
    SETS = {"price": PRICE, "price+dict": PRICE + DICT, "price+finbert": PRICE + FB, "price+jev": PRICE + JEV,
            "all": PRICE + DICT + FB_NP + JEV, "jev_only": JEV}
    E = E[E.jev_ok].copy()
    JEV_DEV_END = pd.Timestamp("2021-06-30")      # base Jev run covers dev filings 2020-01..2021-06
    if MODE == "dev":
        E = E[E.filingDate <= JEV_DEV_END]
JEV_END = E.filingDate.max() if SUB == "jev" else None

E = E[E.has_px & E.gap_x.notna() & (E.filingDate >= (DEV_START if MODE == "dev" else pd.Timestamp("2020-01-01")))].copy()
E["ym"] = E.entry_date.dt.to_period("M")
if MODE == "dev":
    E = E[E.filingDate <= DEV_END]
    E.loc[E[f"end_{H}"] > DEV_PX_END, f"ar_{H}"] = np.nan   # label would peek into the sealed period
E["y"] = np.nan
ok = E[f"ar_{H}"].notna()
E.loc[ok, "y"] = (E.loc[ok, f"ar_{H}"] > E.loc[ok].groupby("ym")[f"ar_{H}"].transform("median")).astype(float)


def ranked(df, cols):
    """Cross-sectional percentile rank within entry month, centred; NaN -> 0 (neutral)."""
    X = df[cols].astype(float).groupby(df.ym).rank(pct=True) - 0.5
    return X.fillna(0.0).values


def model(kind):
    if kind == "logit":
        return LogisticRegression(C=0.1, max_iter=2000)
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=200,
                                          l2_regularization=1.0, random_state=0)


def fit_predict(tr, te, cols, kind):
    m = model(kind)
    trl = tr[tr.y.notna()]
    m.fit(ranked(trl, cols), trl.y.values)
    return m.predict_proba(ranked(te, cols))[:, 1], m


def scores(kind, cols):
    if MODE == "dev":   # purged leave-one-year-out
        s = pd.Series(np.nan, index=E.index)
        folds = ([(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31")) for y in (2020, 2021, 2022)] if SUB == "full" else
                 [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in (("2020-01-01", "2020-06-30"), ("2020-07-01", "2020-12-31"),
                                                                  ("2021-01-01", "2021-06-30"))])
        for y0, y1 in folds:
            inf = E.filingDate.between(y0, y1)
            te = E[inf]
            if len(te) == 0:
                continue
            tr = E[~inf]
            tr = tr[~((tr.entry_date < y0) & (tr[f"end_{H}"] >= y0))]       # labels overlapping the fold
            tr = tr[~((tr.entry_date > y1) & (tr.entry_date <= y1 + pd.Timedelta(days=95)))]  # embargo
            s.loc[te.index] = fit_predict(tr, te, cols, kind)[0]
        return s, None
    raise RuntimeError("test mode handled in main")


def ic_stats(df, col):
    """Monthly (entry month) Spearman IC of score vs H-day excess return; mean, NW t (3 lags), n months."""
    d = df[df[f"ar_{H}"].notna() & df[col].notna()]
    ics = d.groupby("ym").apply(lambda g: spearmanr(g[col], g[f"ar_{H}"])[0] if len(g) >= 20 else np.nan).dropna()
    x = ics.values - ics.values.mean(); n = len(x)
    g0 = (x @ x) / n
    nw = g0 + 2 * sum((1 - L / 4) * (x[L:] @ x[:-L]) / n for L in range(1, 4) if L < n)
    t_nw = ics.mean() / np.sqrt(nw / n) if n > 3 else np.nan
    pooled = spearmanr(d[col], d[f"ar_{H}"])[0]
    return {"ic_mean": ics.mean(), "t_nw": t_nw, "t_iid": ics.mean() / ics.std() * np.sqrt(n), "n_months": n,
            "pooled_ic": pooled, "n_events": len(d)}


# ---------------- portfolio ----------------
px = pd.read_parquet(DATA / "prices.parquet")
if MODE == "dev":
    px = px[px.date <= DEV_PX_END]
O = px.pivot(index="date", columns="ticker", values="Open")
C = px.pivot(index="date", columns="ticker", values="Close")
days = C["SPY"].dropna().index
O, C = O.reindex(days), C.reindex(days)
month_first = pd.Series(days, index=days).groupby(days.to_period("M")).first()
REB = [d for d in month_first.values if d >= pd.Timestamp("2020-02-01")]
if MODE == "test":
    REB = [d for d in month_first.values if d >= TEST_START]
if SUB == "jev":   # stop when the eligible set would include releases after Jev coverage ends
    REB = [d for d in REB if d <= month_first[(JEV_END + pd.offsets.MonthBegin(1)).to_period("M")]]
REB = pd.DatetimeIndex(REB)
pos = pd.Series(np.arange(len(days)), index=days)


def valuation(tk, i0, i1):
    """Gross return of a position bought at open of day i0 and valued at open of i1 (or close of the last day
    if i1 == len(days)); a name that stops trading is valued at its last close (cash afterwards)."""
    o = O[tk].values; c = C[tk].values
    if not np.isfinite(o[i0]):
        return np.nan
    if i1 < len(days) and np.isfinite(o[i1]):
        return o[i1] / o[i0]
    cc = c[i0:min(i1, len(days))]; ok = np.isfinite(cc)
    return cc[ok][-1] / o[i0] if ok.any() else np.nan


def backtest(df, col, topn=TOPN, cost_bp=COST_BP):
    rets, tos, held_all, nel = [], [], [], []
    w_prev = pd.Series(dtype=float)
    for k, d in enumerate(REB):
        i0 = pos[d]; i1 = pos[REB[k + 1]] if k + 1 < len(REB) else len(days)
        if i1 <= i0:
            continue
        lo = days[max(i0 - LOOKBACK, 0)]
        el = df[(df.entry_date < d) & (df.entry_date >= lo) & df[col].notna()]
        el = el.sort_values("entry_date").drop_duplicates("ticker", keep="last")
        el = el[el.ticker.isin(O.columns)]
        el = el[np.isfinite(O.loc[d, el.ticker].values.astype(float))]
        if len(el) < 50:
            continue
        pick = el.nlargest(topn, col).ticker.tolist() if topn else el.ticker.tolist()
        w = pd.Series(1.0 / len(pick), index=pick)
        to = w.subtract(w_prev, fill_value=0).abs().sum()
        g = pd.Series({t: valuation(t, i0, i1) for t in pick}).fillna(1.0)
        gross = (w * g).sum()
        net = gross - 1 - to * cost_bp / 1e4
        spy = valuation("SPY", i0, i1)
        rets.append((d, net, gross - 1, spy - 1, to)); nel.append(len(el))
        w_prev = (w * g) / gross     # drifted weights at the next rebalance
        held_all += pick
    R = pd.DataFrame(rets, columns=["date", "net", "gross", "spy", "turnover"]).set_index("date")
    return R, np.mean(nel), len(set(held_all))


def perf(r, yrs):
    eq = (1 + r).cumprod()
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "maxdd": (eq / eq.cummax() - 1).min(), "vol": r.std() * np.sqrt(12)}


def run_all(df, score_cols):
    out = []
    for name, col in score_cols.items():
        R, nel, nnames = backtest(df, col)
        span = (days[min(pos[REB[-1]] + 21, len(days) - 1)] - R.index[0]).days / 365.25
        yrs = len(R) / 12
        net = perf(R.net, yrs); gross = perf(R.gross, yrs); spy = perf(R.spy, yrs)
        r2 = R.gross - R.turnover * 2 * COST_BP / 1e4
        net2 = perf(r2, yrs)
        te = (R.net - R.spy)
        out.append({"model": name, "months": len(R), "cagr_gross": gross["cagr"], "cagr_net": net["cagr"],
                    "cagr_net_2x": net2["cagr"], "cagr_spy": spy["cagr"], "excess_net": net["cagr"] - spy["cagr"],
                    "excess_net_2x": net2["cagr"] - spy["cagr"], "maxdd": net["maxdd"], "maxdd_spy": spy["maxdd"],
                    "vol": net["vol"], "ir_vs_spy": te.mean() / te.std() * np.sqrt(12),
                    "turnover_pm": R.turnover.mean(), "avg_eligible": nel, "distinct_names": nnames})
        R.to_parquet(DATA / f"monthly_{MODE}_{SUB}_{name.replace('+', '_')}.parquet")
    return pd.DataFrame(out)


if __name__ == "__main__":
    score_cols, ic_rows = {}, []
    if MODE == "dev":
        for kind in ("logit", "gbt"):
            for sname, cols in SETS.items():
                c = f"s_{kind}_{sname}"
                E[c], _ = scores(kind, cols)
                score_cols[c] = c
                ic_rows.append({"score": c, **ic_stats(E, c)})
                print(c, {k: round(v, 4) for k, v in ic_rows[-1].items() if isinstance(v, float)}, flush=True)
    else:
        # final models: fit on every dev event whose label ended by 2022-12-30; score events filed from
        # 2022-10 (so the first test rebalance on 2023-01-03 has a full eligible set); IC on 2023+ filings only
        tr = E[(E.filingDate <= DEV_END) & (E[f"end_{H}"] <= DEV_PX_END)]
        if SUB == "jev":
            tr = tr[tr.filingDate <= JEV_DEV_END]   # identical training events for all four sets
        te_mask = E.filingDate >= pd.Timestamp("2022-10-01")
        coefs = {}
        for kind in ("logit", "gbt"):
            for sname, cols in SETS.items():
                c = f"s_{kind}_{sname}"
                E[c] = np.nan
                E.loc[te_mask, c], m = fit_predict(tr, E[te_mask], cols, kind)
                score_cols[c] = c
                if kind == "logit":
                    coefs[sname] = pd.Series(m.coef_[0], index=cols)
                ic_rows.append({"score": c, **ic_stats(E[E.filingDate >= TEST_START], c)})
                print(c, {k: round(v, 4) for k, v in ic_rows[-1].items() if isinstance(v, float)}, flush=True)
        pd.concat(coefs, names=["set", "feature"]).rename("coef").to_csv(RES / f"coefs_final_{SUB}.csv")
    E["s_control_all"] = 0.0     # no-skill control: hold every eligible name
    pd.DataFrame(ic_rows).to_csv(RES / f"ic_{MODE}_{SUB}.csv", index=False)
    E.to_parquet(DATA / f"events_{MODE}_{SUB}_oof.parquet")
    res = run_all(E, score_cols)
    Rc, nel, _ = backtest(E, "s_control_all", topn=None)
    yrs = len(Rc) / 12
    ctrl = {"model": "control_all_eligible_EW", "months": len(Rc), "cagr_net": perf(Rc.net, yrs)["cagr"],
            "cagr_spy": perf(Rc.spy, yrs)["cagr"], "maxdd": perf(Rc.net, yrs)["maxdd"], "turnover_pm": Rc.turnover.mean(),
            "avg_eligible": nel}
    ctrl["excess_net"] = ctrl["cagr_net"] - ctrl["cagr_spy"]
    res = pd.concat([res, pd.DataFrame([ctrl])])
    res.to_csv(RES / f"results_{MODE}_{SUB}.csv", index=False)
    pd.set_option("display.width", 250)
    print(res.round(4).to_string())
