"""Sealed TEST run (2013-01-01 -> latest). Run ONCE, after PREREG.md. Frozen rule from lib.py (see PREREG.md).
Primary: ridge coefficients and standardisation frozen on all DEV events (alpha*n = 1.0), feature set c_jev.
Also reported (same frozen procedure): a_notext, b_dict, neutral allocator, SPY, 60/40; expanding-refit variant;
close and next-open execution; 3bp and 6bp per side.
Writes research/round6/j03_fomc/test_results.txt
"""
import io
import pathlib

import numpy as np
import pandas as pd

import lib

OUT = pathlib.Path(__file__).resolve().parent
DEV_END, TEST_START = "2012-12-31", "2013-01-01"
buf = io.StringIO()


def say(*a):
    print(*a)
    print(*a, file=buf)


def ic(z, y):
    ok = np.isfinite(z) & np.isfinite(y)
    return np.corrcoef(z[ok], y[ok])[0, 1] if ok.sum() > 5 else np.nan


def main():
    if not (OUT / "PREREG.md").exists():
        raise SystemExit("PREREG.md missing: TEST is sealed")
    px = lib.load_prices()
    ev_all = lib.add_targets(lib.load_events(), px)
    dev = ev_all[ev_all.event_date <= DEV_END]
    test_end = px.index[-1]
    first = ev_all[ev_all.event_date >= TEST_START].event_date.iloc[0]
    say(f"TEST window: first TEST event {first.date()} -> {test_end.date()}; events {int((ev_all.event_date >= TEST_START).sum())}")
    r_spy = px.SPY_cc.loc[first:test_end].iloc[1:]
    r_6040 = lib.static_60_40(px, first, test_end)[0]
    m_spy, m_6040 = lib.metrics(r_spy), lib.metrics(r_6040)
    say("SPY  ", {k: round(v, 2) for k, v in m_spy.items()})
    say("60/40", {k: round(v, 2) for k, v in m_6040.items()})
    rows, rets = [], {}
    NEU = lib.weights_from_z(0.0, 0.0, True)   # start neutral so day 1 carries no same-bar signal
    for name, cols in lib.FEATS.items():
        for mode in ("frozen", "refit"):
            if mode == "frozen":
                fz = lib.fit_models(dev, cols)
                p = lib.walk_forward(ev_all, cols, TEST_START, test_end, frozen=fz)
            else:
                p = lib.walk_forward(ev_all, cols, TEST_START, test_end)
            p.to_parquet(lib.D / f"test_preds_{name}_{mode}.parquet")
            sched = lib.schedule(p, px)
            row = dict(set=name, mode=mode, n=len(p), ic_eq=ic(p.z_eq.values, p.y_eq.values), ic_dur=ic(p.z_dur.values, p.y_dur.values))
            for ex in ("close", "open"):
                for cb in (3.0, 6.0):
                    r, to = lib.backtest(sched, px, first, test_end, cb, ex, init=NEU)
                    m = lib.metrics(r)
                    row[f"CAGR_{ex}_{int(cb)}bp"] = m["CAGR"]
                    if ex == "open" and cb == 3.0:   # PRIMARY execution (PREREG): next open, 3bp/side
                        row.update(vol=m["vol"], sharpe=m["sharpe"], maxDD=m["maxDD"], turnover_x=to,
                                   vs_SPY=m["CAGR"] - m_spy["CAGR"], vs_6040=m["CAGR"] - m_6040["CAGR"])
                        rets[(name, mode)] = r
                    if ex == "open" and cb == 6.0:
                        row["vs_SPY_6bp"] = m["CAGR"] - m_spy["CAGR"]
            rows.append(row)
    neutral = lib.schedule(p, px, neutral=True)
    for ex in ("close", "open"):
        for cb in (3.0, 6.0):
            m = lib.metrics(lib.backtest(neutral, px, first, test_end, cb, ex)[0])
            say(f"neutral allocator {ex} {cb}bp:", {k: round(v, 2) for k, v in m.items()})
    r_neu = lib.backtest(neutral, px, first, test_end, 3.0, "open")[0]
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    say(res.round(3).to_string(index=False))
    per = pd.Series(np.searchsorted(ev_all.event_date.values, r_neu.index.values), index=r_neu.index)
    for nm, x, y in (("c - b (frozen)", rets[("c_jev", "frozen")], rets[("b_dict", "frozen")]),
                     ("c - neutral (frozen)", rets[("c_jev", "frozen")], r_neu),
                     ("c - SPY (frozen)", rets[("c_jev", "frozen")], r_spy.reindex(r_neu.index).fillna(0)),
                     ("c - b (refit)", rets[("c_jev", "refit")], rets[("b_dict", "refit")])):
        dlt = (np.log1p(x) - np.log1p(y)).groupby(per).sum()
        say(f"  {nm:22s}: {dlt.sum() / (len(x) / 252) * 100:6.2f} pts/yr (log), t = {dlt.mean() / (dlt.std() / np.sqrt(len(dlt))):5.2f}")
    # yearly table for the primary
    yr = pd.DataFrame({"c_jev": rets[("c_jev", "frozen")], "b_dict": rets[("b_dict", "frozen")], "neutral": r_neu,
                       "SPY": r_spy.reindex(r_neu.index).fillna(0), "60/40": r_6040.reindex(r_neu.index).fillna(0)})
    say("\nCalendar-year returns (%), next-open execution, 3bp:")
    say((((1 + yr).groupby(yr.index.year).prod() - 1) * 100).round(1).to_string())
    (OUT / "test_results.txt").write_text(buf.getvalue())
    res.to_csv(OUT / "test_results.csv", index=False)


if __name__ == "__main__":
    main()
