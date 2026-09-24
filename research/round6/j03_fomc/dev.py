"""DEV evaluation (events 1994-2012 only). Walk-forward, expanding window, OOS from 2000-01-01.
Nested feature sets a/b/c on identical events and dates; backtests at 3bp and 6bp per side, close and next-open.
Writes research/round6/j03_fomc/dev_results.txt and data/round6/j03_fomc/dev_preds_<set>.parquet
"""
import io
import os
import pathlib
import sys

import numpy as np
import pandas as pd

import lib

OUT = pathlib.Path(__file__).resolve().parent
DEV_END = "2012-12-31"
OOS_START = "2000-01-01"
buf = io.StringIO()


def say(*a):
    print(*a)
    print(*a, file=buf)


def ic(z, y):
    ok = np.isfinite(z) & np.isfinite(y)
    if ok.sum() < 5:
        return np.nan, np.nan
    return (np.corrcoef(z[ok], y[ok])[0, 1], pd.Series(z[ok]).corr(pd.Series(y[ok]), method="spearman"))


def main():
    px = lib.load_prices()
    ev = lib.add_targets(lib.load_events(), px)
    ev = ev[ev.event_date <= DEV_END].reset_index(drop=True)
    say(f"DEV events: {len(ev)}  (S={int((ev.kind=='S').sum())}, M={int((ev.kind=='M').sum())}); OOS from {OOS_START}")
    say("Holding period (days between events): median", ev.next_date.sub(ev.event_date).dt.days.median())

    # descriptive: do next-period returns line up with the day's 2y yield move?
    for k in ("S", "M"):
        s = ev[ev.kind == k]
        say(f"[{k}] corr(dy2 on day, next-period SPY xs) = {s.dy2_bp.corr(s.y_eq):.3f}; with TLT xs = {s.dy2_bp.corr(s.y_dur):.3f} (n={len(s)})")

    start_bt = ev[ev.event_date >= OOS_START].event_date.iloc[0]
    end_bt = DEV_END
    res, preds_all = [], {}
    for alpha in (1.0, 0.1, 10.0):
        for name, cols in lib.FEATS.items():
            p = lib.walk_forward(ev, cols, OOS_START, DEV_END, alpha_per_n=alpha)
            preds_all[(name, alpha)] = p
            ice, ice_s = ic(p.z_eq.values, p.y_eq.values)
            icd, icd_s = ic(p.z_dur.values, p.y_dur.values)
            row = dict(set=name, alpha=alpha, n=len(p), ic_eq=ice, ric_eq=ice_s, ic_dur=icd, ric_dur=icd_s)
            for k in ("S", "M"):
                q = p[p.kind == k]
                row[f"ic_eq_{k}"], _ = ic(q.z_eq.values, q.y_eq.values)
                row[f"ic_dur_{k}"], _ = ic(q.z_dur.values, q.y_dur.values)
            sched = lib.schedule(p, px)
            for ex in ("close", "open"):
                for cb in (3.0, 6.0):
                    r, to = lib.backtest(sched, px, start_bt, end_bt, cb, ex)
                    m = lib.metrics(r)
                    row[f"CAGR_{ex}_{int(cb)}bp"] = m["CAGR"]
                    if ex == "close" and cb == 3.0:
                        row.update(vol=m["vol"], sharpe=m["sharpe"], maxDD=m["maxDD"], turnover_x=to)
                        preds_all[(name, alpha, "ret")] = r
            res.append(row)
            if alpha == 1.0:
                p.to_parquet(lib.D / f"dev_preds_{name}.parquet")
    res = pd.DataFrame(res)
    # benchmarks
    neutral = lib.schedule(preds_all[("a_notext", 1.0)], px, neutral=True)
    bm = {}
    for ex in ("close", "open"):
        for cb in (3.0, 6.0):
            bm[f"neutral_{ex}_{int(cb)}"] = lib.metrics(lib.backtest(neutral, px, start_bt, end_bt, cb, ex)[0])
    r_neu = lib.backtest(neutral, px, start_bt, end_bt, 3.0, "close")[0]
    r_spy = px.SPY_cc.loc[start_bt:end_bt].iloc[1:]
    r_6040 = lib.static_60_40(px, start_bt, end_bt)[0]
    say(f"\nBacktest window {start_bt.date()} -> {end_bt} (walk-forward OOS inside DEV). Costs 3bp/side (and 6bp).")
    say("Benchmarks: SPY", {k: round(v, 2) for k, v in lib.metrics(r_spy).items()})
    say("            60/40 SPY/IEF", {k: round(v, 2) for k, v in lib.metrics(r_6040).items()})
    say("            neutral allocator (same menu, z=0)", {k: round(v, 2) for k, v in bm["neutral_close_3"].items()},
        "| next-open 3bp CAGR", round(bm["neutral_open_3"]["CAGR"], 2))
    pd.set_option("display.width", 250)
    say("\nOOS information coefficients and backtests by feature set and ridge penalty (alpha*n):")
    say(res.round(3).to_string(index=False))

    # paired test on per-day returns vs neutral and c vs b (alpha=1)
    say("\nPaired differences (alpha=1, close, 3bp): annualised mean diff, t-stat on event-period returns")
    ra, rb, rc = (preds_all[(n, 1.0, "ret")] for n in ("a_notext", "b_dict", "c_jev"))
    per = pd.Series(np.searchsorted(ev.event_date.values, ra.index.values, side="left"), index=ra.index)
    for nm, x, y in (("a - neutral", ra, r_neu), ("b - neutral", rb, r_neu), ("c - neutral", rc, r_neu), ("c - b", rc, rb),
                     ("c - SPY", rc, r_spy.reindex(rc.index).fillna(0))):
        dlt = (np.log1p(x) - np.log1p(y)).groupby(per).sum()
        t = dlt.mean() / (dlt.std() / np.sqrt(len(dlt)))
        say(f"  {nm:12s}: {dlt.sum() / (len(x) / 252) * 100:6.2f} pts/yr (log), t = {t:5.2f}, periods = {len(dlt)}")

    # power: SE of IC with n OOS events
    n = res.n.iloc[0]
    say(f"\nPower: {n} OOS events -> SE(IC) ~ {1 / np.sqrt(n):.3f}; 2-sigma detectable IC ~ {2 / np.sqrt(n):.3f}. "
        f"Holding periods overlap none (event-to-event), so n is the effective sample.")

    # full-DEV fit coefficients (c set) and ablation of each Jev feature (OOS IC, alpha=1)
    models, tr = lib.fit_models(ev, lib.FEATS["c_jev"])
    coef = pd.DataFrame({t: models[t][0][1:] for t in ("y_eq", "y_dur")}, index=lib.FEATS["c_jev"])
    say("\nFull-DEV ridge coefficients (c set, standardised features, target in % excess return per period):")
    say(coef.round(3).to_string())
    base = res[(res.set == "c_jev") & (res.alpha == 1.0)].iloc[0]
    say("\nAblation (drop one Jev feature; OOS IC eq / dur, alpha=1). Base c:", round(base.ic_eq, 3), round(base.ic_dur, 3))
    for f in ["J_hawk", "J_guid", "J_infl", "J_bs", "J_risk"]:
        cols = [c for c in lib.FEATS["c_jev"] if c != f]
        p = lib.walk_forward(ev, cols, OOS_START, DEV_END)
        say(f"  -{f:7s}: ic_eq {ic(p.z_eq.values, p.y_eq.values)[0]:.3f}  ic_dur {ic(p.z_dur.values, p.y_dur.values)[0]:.3f}")
    # univariate OOS-free descriptive correlations of each feature with next-period returns (whole DEV)
    say("\nUnivariate corr of each feature with next-period excess returns (all DEV events, descriptive):")
    rows = []
    for f in lib.FEATS["c_jev"]:
        rows.append(dict(feature=f, corr_eq=ev[f].astype(float).corr(ev.y_eq), corr_dur=ev[f].astype(float).corr(ev.y_dur),
                         corr_eq_S=ev[ev.kind == "S"][f].astype(float).corr(ev[ev.kind == "S"].y_eq),
                         corr_eq_M=ev[ev.kind == "M"][f].astype(float).corr(ev[ev.kind == "M"].y_eq)))
    say(pd.DataFrame(rows).round(3).to_string(index=False))
    (OUT / "dev_results.txt").write_text(buf.getvalue())
    res.to_csv(OUT / "dev_results.csv", index=False)


if __name__ == "__main__":
    main()
