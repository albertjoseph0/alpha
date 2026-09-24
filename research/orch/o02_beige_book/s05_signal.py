"""Signal-level evaluation on DEV (2000-2015; data from load_etf_dev only) and the leakage probe.

Per Beige Book release j (DEV decision days in 2000-2015; ~128 releases):
  period return of each ETF = compounded daily returns after the harness trade day of release j
  through the trade day of release j+1 (trade day = decision day + 1, exactly as in the harness).
Reports, for each score (mom, dict, lm, jev, nested composites):
  * cross-sectional Spearman IC vs the period return (mean, t, share > 0);
  * top-3 minus equal-weight-9 spread per period (mean, t, annualised), and paired differences between
    variants (c vs b, jev vs mom), with the minimum detectable effect at 80% power;
  * timing: the `overall` score vs next-period SPY and defensive-minus-cyclical returns;
  * per-ETF time-series correlation (which sector mappings carry signal).
Leakage probe (DEV docs whose 6-month outcome ends by 2015-12-31): AUC of Jev's "did stocks rise over the next
6 months" vs realized SPY 6-month return > 0, compared with the AUC of the legit content scores; the sector
probe's rank correlation with realized 6-month sector returns and top-1 hit rate (chance = 1/9).
Also Jev answer diagnostics: 'not mentioned' share and max-probability confidence by era (from the free cache).
Outputs: data/orch/o02_beige_book/signal_dev.csv, periods_dev.parquet, probe_dev.csv; the summary is printed.
"""
import gzip
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from common import D, DEFENSIVE, ETFS, K, composite, load_text_scores, momentum, rebalance_days, releases, top_k  # noqa: E402
from harness.data import load_etf_dev  # noqa: E402

VARS = ["mom", "dict", "lm", "jev", "mom+dict", "mom+dict+jev", "mom+jev", "dict+jev"]
DEV0, DEV1 = pd.Timestamp("2000-01-01"), pd.Timestamp("2015-12-31")


def auc(score, label):
    s, y = np.asarray(score, float), np.asarray(label, bool)
    m = ~np.isnan(s)
    s, y = s[m], y[m]
    if y.all() or (~y).all():
        return np.nan, np.nan, 0
    u = stats.mannwhitneyu(s[y], s[~y]).statistic
    a = u / (y.sum() * (~y).sum())
    n1, n0 = y.sum(), (~y).sum()   # Hanley-McNeil SE
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = np.sqrt((a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0))
    return a, se, len(s)


def main():
    data = load_etf_dev()
    R = data.returns[ETFS + ["SPY"]]
    cal = data.dates
    mom = momentum(R[ETFS])
    text = load_text_scores()
    reb = rebalance_days(cal, releases())
    reb = reb[(reb >= cal[cal.searchsorted(DEV0) - 2]) & (reb <= DEV1)]
    trade = pd.DatetimeIndex([cal[cal.get_loc(d) + 1] if cal.get_loc(d) + 1 < len(cal) else pd.NaT for d in reb.values])
    lr = np.log1p(R.fillna(0.0)).cumsum()
    rows = []
    for j in range(len(reb)):
        t0 = trade[j]
        t1 = trade[j + 1] if j + 1 < len(reb) and not pd.isna(trade[j + 1]) else cal[-1]
        if pd.isna(t0) or t1 <= t0:
            continue
        pr = np.expm1(lr.loc[t1] - lr.loc[t0])
        r, d0 = reb.index[j], reb.iloc[j]
        row = {"release": r, "decision": d0, "t0": t0, "t1": t1}
        row.update({f"ret_{e}": pr[e] for e in ETFS + ["SPY"]})
        row.update({f"mom_{e}": mom.loc[d0, e] for e in ETFS})
        for src in ("dict", "lm", "jev"):
            row.update({f"{src}_{e}": text[src].loc[r, e] for e in ETFS})
        rows.append(row)
    P = pd.DataFrame(rows).set_index("release")
    P.to_parquet(D / "periods_dev.parquet")
    n = len(P)
    yrs = (P.t1.iloc[-1] - P.t0.iloc[0]).days / 365.25
    ppy = n / yrs
    ret = P[[f"ret_{e}" for e in ETFS]].set_axis(ETFS, axis=1)
    ew = ret.mean(axis=1)
    print(f"DEV periods: {n} releases, {P.t0.iloc[0].date()} -> {P.t1.iloc[-1].date()} ({yrs:.1f}y, {ppy:.2f}/yr)")

    def score(v, idx):
        parts = [P.loc[idx, [f"{p}_{e}" for e in ETFS]].set_axis(ETFS).astype(float) for p in v.split("+")]
        return parts[0] if len(parts) == 1 else composite(parts)

    out, top = [], {}
    for v in VARS:
        ic, tr = [], []
        for idx in P.index:
            s = score(v, idx)
            ic.append(stats.spearmanr(s, ret.loc[idx]).statistic if s.nunique() > 1 else np.nan)
            w = top_k(s, K)
            tr.append(float((w * ret.loc[idx]).sum()) if w.notna().all() else ew.loc[idx])
        ic, tr = np.array(ic), pd.Series(tr, index=P.index)
        top[v] = tr
        sp = np.log1p(tr) - np.log1p(ew)
        out.append({"variant": v, "ic_mean": np.nanmean(ic), "ic_t": np.nanmean(ic) / np.nanstd(ic, ddof=1) * np.sqrt(np.isfinite(ic).sum()),
                    "ic_pos": np.nanmean(ic > 0), "spread_ann_logpct": sp.mean() * ppy * 100,
                    "spread_t": sp.mean() / sp.std(ddof=1) * np.sqrt(n),
                    "mde80_ann_pct": 2.8 * sp.std(ddof=1) * np.sqrt(ppy) / np.sqrt(yrs) * 100})
    S = pd.DataFrame(out).set_index("variant")
    S.to_csv(D / "signal_dev.csv")
    print("\nSignal quality vs next-period returns (DEV, gross of costs). spread = top-3 minus EW9, log, annualised:")
    print(S.round(3).to_string())

    print("\nPaired differences (per-period log return of top-3, annualised pp; t):")
    for a, b in [("mom+dict+jev", "mom+dict"), ("jev", "dict"), ("jev", "mom"), ("mom+jev", "mom"), ("dict", "mom"), ("dict+jev", "dict")]:
        d = np.log1p(top[a]) - np.log1p(top[b])
        print(f"  {a:>13s} - {b:<9s} {d.mean() * ppy * 100:+6.2f} pp/yr   t={d.mean() / d.std(ddof=1) * np.sqrt(n):+.2f}   "
              f"MDE80={2.8 * d.std(ddof=1) * np.sqrt(ppy) / np.sqrt(yrs) * 100:.1f} pp/yr")

    # timing: overall direction vs SPY and defensives-minus-cyclicals
    cyc = [e for e in ETFS if e not in DEFENSIVE]
    dmc = ret[DEFENSIVE].mean(axis=1) - ret[cyc].mean(axis=1)
    print("\nTiming (Spearman, n=%d): overall direction vs next-period returns" % n)
    for src in ("dict", "lm", "jev"):
        ov = -P[f"{src}_XLP"]   # defensive score = -overall
        a = stats.spearmanr(ov, P.ret_SPY)
        b = stats.spearmanr(ov, dmc)
        print(f"  {src:5s} overall vs SPY rho={a.statistic:+.3f} (p={a.pvalue:.2f});  vs defensive-minus-cyclical rho={b.statistic:+.3f} (p={b.pvalue:.2f})")

    print("\nPer-ETF time-series corr (score minus cross-section mean vs return minus EW), which mappings carry signal:")
    rel = ret.sub(ew, axis=0)
    tab = {}
    for src in ("mom", "dict", "jev"):
        sc = P[[f"{src}_{e}" for e in ETFS]].set_axis(ETFS, axis=1).astype(float)
        sc = sc.sub(sc.mean(axis=1), axis=0)
        tab[src] = {e: stats.spearmanr(sc[e], rel[e]).statistic for e in ETFS}
    print(pd.DataFrame(tab).round(3).to_string())

    # holdings: share of periods where the Jev rule holds each ETF
    hold = pd.DataFrame({idx: top_k(score("jev", idx), K) for idx in P.index}).T
    print("\nJev top-3: average weight per ETF over DEV:", (hold.mean() * 100).round(1).to_dict())
    print("Jev top-3: share of periods fully defensive (XLP+XLU+XLV = 100%):",
          round(float((hold[DEFENSIVE].sum(axis=1) > 0.999).mean()), 3))
    probe(data, text)
    jev_diagnostics()


def probe(data, text):
    pr = pd.read_parquet(D / "probe.parquet")
    pr.index = pd.to_datetime(pr.release)
    R = data.returns
    cal = data.dates
    lr = np.log1p(R.fillna(0.0)).cumsum()
    js = pd.read_parquet(D / "jev_scores.parquet")
    js.index = pd.to_datetime(js.release)
    dct = pd.read_parquet(D / "dict_scores.parquet")
    dct.index = pd.to_datetime(dct.release)
    rows = []
    for r in pr.index:
        i0 = cal.searchsorted(r, side="left")        # release-day close (report out at 14:00)
        i1 = i0 + 126
        if i1 >= len(cal) or r < pd.Timestamp("1996-01-01"):
            continue
        spy6 = np.expm1(lr["SPY"].iloc[i1] - lr["SPY"].iloc[i0])
        sec6 = np.expm1(lr[ETFS].iloc[i1] - lr[ETFS].iloc[i0]) if R[ETFS].iloc[i0 - 250:i0].notna().all().all() else None
        rows.append({"release": r, "probe": pr.loc[r, "probe"], "spy6": spy6, "up": spy6 > 0,
                     "jev_overall": js.loc[r, "overall"], "jev_outlook": js.loc[r, "outlook"],
                     "dict_overall": dct.loc[r, "d_overall"],
                     **({f"sec6_{e}": sec6[e] for e in ETFS} if sec6 is not None else {})})
    Q = pd.DataFrame(rows).set_index("release")
    Q.to_csv(D / "probe_dev.csv")
    print(f"\nLEAKAGE PROBE (DEV docs with a 6-month outcome inside DEV: n={len(Q)}, {Q.index[0].date()}..{Q.index[-1].date()}, "
          f"share up={Q.up.mean():.2f})")
    for c in ("probe", "jev_overall", "jev_outlook", "dict_overall"):
        a, se, m = auc(Q[c], Q.up)
        print(f"  AUC {c:13s} = {a:.3f} (SE {se:.3f}, n={m})")
    a, se, m = auc(Q.probe[Q.index >= "2000-01-01"], Q.up[Q.index >= "2000-01-01"])
    print(f"  AUC probe, 2000+ only = {a:.3f} (SE {se:.3f}, n={m})")
    print(f"  Spearman probe vs SPY 6m return: {stats.spearmanr(Q.probe, Q.spy6).statistic:+.3f}")
    print(f"  probe mean {Q.probe.mean():.3f}, sd {Q.probe.std():.3f}")
    # sector probe
    m = {"materials": "XLB", "energy": "XLE", "financials": "XLF", "industrials": "XLI", "technology": "XLK",
         "consumer_staples": "XLP", "utilities": "XLU", "health_care": "XLV", "consumer_discretionary": "XLY"}
    Qs = Q.dropna(subset=[f"sec6_{e}" for e in ETFS])
    ics, hits, hits_rand = [], [], []
    for r in Qs.index:
        p = pd.Series({m[k]: pr.loc[r, f"ps_{k}"] for k in m})
        y = pd.Series({e: Qs.loc[r, f"sec6_{e}"] for e in ETFS})
        ics.append(stats.spearmanr(p[ETFS], y[ETFS]).statistic)
        hits.append(p.idxmax() == y.idxmax())
    ics = np.array(ics)
    print(f"  sector probe (n={len(Qs)}): mean rank corr {np.nanmean(ics):+.3f} (t={np.nanmean(ics) / np.nanstd(ics, ddof=1) * np.sqrt(len(ics)):+.2f}), "
          f"top-1 hit {np.mean(hits):.3f} vs chance {1 / 9:.3f} (binomial p={stats.binomtest(int(np.sum(hits)), len(hits), 1 / 9).pvalue:.2f})")


def jev_diagnostics():
    sys.path.insert(0, str(D.parents[2] / "research" / "round5"))
    from jev import ask
    from s02_jev import AGENT, SECTORS, national_summary, questions
    ed = [json.loads(l) for l in gzip.open(D / "editions_fixed.jsonl.gz", "rt")]
    Q = questions()
    rows = []
    for e in ed:
        a = ask(national_summary(e["text"]), Q, agent=AGENT)   # cached: free
        row = {"release": e["release"]}
        for k in SECTORS:
            p = a[k]["probabilities"]
            row["nm_" + k] = p.get("not_mentioned", 0.0)
            row["conf_" + k] = max(p.values())
        rows.append(row)
    df = pd.DataFrame(rows)
    era = np.where(pd.to_datetime(df.release) < "2017-01-01", "pre-2017", "2017+")
    nm = df[[c for c in df if c.startswith("nm_")]]
    cf = df[[c for c in df if c.startswith("conf_")]]
    print("\nJev answer diagnostics by era: share 'not mentioned' (p>=0.5) and mean max-probability")
    t = pd.concat({"not_mentioned": (nm >= 0.5).groupby(era).mean().T, "confidence": cf.groupby(era).mean().T}, axis=1)
    t.index = [i.split("_", 1)[1] for i in t.index]
    print(t.round(2).to_string())
    allc = cf.to_numpy().ravel()
    print("confidence quantiles (all answers):", np.round(np.quantile(allc, [0.1, 0.25, 0.5, 0.75, 0.9]), 2).tolist())
    df.to_csv(D / "jev_diagnostics.csv", index=False)


if __name__ == "__main__":
    main()
