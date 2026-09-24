"""DEV / TEST analysis driver.   usage: python 06_analyze.py prep|dev|test
prep : match prices for every event, cache to data folder
dev  : events filed 2006-2015 only
test : events filed 2016+ (run ONCE after PREREG.md is frozen)"""
import sys, os, pickle, zlib, importlib.util
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bt", f"{HERE}/05_backtest.py")
bt = importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)
D = bt.D
CACHE = f"{D}/prepared.pkl"


def get_prepared():
    if not os.path.exists(CACHE):
        out = bt.prepare()
        pickle.dump(out, open(CACHE, "wb"))
    return pickle.load(open(CACHE, "rb"))


def hash01(k):
    return (zlib.crc32(str(k).encode()) % 10000) / 10000.0


# ---------------- universe + variants ----------------
def base_mask(ev):
    """price/liquidity/size universe for matched events (data up to filing-date close)."""
    return ((ev.status == "ok") & (ev.price >= 2) & (ev.vwap >= 2) & (ev.adv >= 1e5)
            & ~(ev.mcap > 1e10))


SEC_FILTERS = {  # filters computable from SEC data alone (apply to missing names too)
    "base": lambda e: pd.Series(True, e.index),
    "opportunistic(n_opp>=3)": lambda e: e.n_opp >= 3,
    "big_buys(med pct_hold>=10%)": lambda e: e.med_pct_hold >= 0.10,
    "ceo_or_cfo_in_cluster": lambda e: e.has_ceo_cfo,
    "n_ins>=4": lambda e: e.n_ins >= 4,
    "n_ins>=5": lambda e: e.n_ins >= 5,
}
PX_FILTERS = {   # need prices
    "after_decline(ret63<0)": lambda e: e.ret63 < 0,
}


def variant_mask(ev, name):
    if name in SEC_FILTERS:
        return SEC_FILTERS[name](ev).fillna(False)
    if name in PX_FILTERS:
        return PX_FILTERS[name](ev).fillna(False)
    if name == "all4(opp+big+ceo/cfo+decline)":
        return (SEC_FILTERS["opportunistic(n_opp>=3)"](ev) & SEC_FILTERS["big_buys(med pct_hold>=10%)"](ev)
                & SEC_FILTERS["ceo_or_cfo_in_cluster"](ev) & PX_FILTERS["after_decline(ret63<0)"](ev)).fillna(False)
    raise KeyError(name)


VARIANTS = ["base", "opportunistic(n_opp>=3)", "big_buys(med pct_hold>=10%)", "ceo_or_cfo_in_cluster",
            "after_decline(ret63<0)", "all4(opp+big+ceo/cfo+decline)", "n_ins>=4", "n_ins>=5"]


def missing_set(ev, per, name):
    """events with no usable price, price>=$2 by the insiders' own reported price, subsampled at the
    pass rate of the price-based universe filters observed among matched events of the same year."""
    m = ev[(ev.status != "ok") & (ev.vwap >= 2) & per]
    m = m[variant_mask(m, name) if name in SEC_FILTERS else pd.Series(True, m.index)]
    ok = ev[(ev.status == "ok") & (ev.vwap >= 2) & per]
    okm = variant_mask(ok, name) if name in SEC_FILTERS else pd.Series(True, ok.index)
    ok = ok[okm]
    passed = base_mask(ok) & (variant_mask(ok, name) if name not in SEC_FILTERS else True)
    rate = passed.groupby(ok.fdate.dt.year).mean()
    keep = [hash01(k) < rate.get(y, rate.mean()) for k, y in zip(m.index, m.fdate.dt.year)]
    return m[np.array(keep, bool)]


def run_variant(ev, paths, bench, per, name, H=126, start=None, end=None, top_cut=True):
    sel = ev[per & base_mask(ev) & variant_mask(ev, name)]
    miss = missing_set(ev, per, name)
    r = {"variant": name, "H": H, "n_events": len(sel), "n_missing": len(miss),
         "miss_frac": len(miss) / max(1, len(sel) + len(miss))}
    eq, nact = bt.simulate(sel, paths, bench, H=H, start=start, end=end)
    r["cagr"] = bt.cagr(eq); r["maxdd"] = bt.maxdd(eq); r["avg_pos"] = float(nact.mean())
    r["cagr_2x"] = bt.cagr(bt.simulate(sel, paths, bench, H=H, start=start, end=end, cost_mult=2)[0])
    r["cagr_0x"] = bt.cagr(bt.simulate(sel, paths, bench, H=H, start=start, end=end, cost_mult=0)[0])
    for mr, lab in [(-0.5, "miss-50"), (-1.0, "miss-100")]:
        r[f"cagr_{lab}"] = bt.cagr(bt.simulate(sel, paths, bench, H=H, start=start, end=end,
                                               missing=miss, missing_ret=mr)[0])
    if top_cut and len(sel) > 100:
        hp = sel[f"hpr{H}"]
        cut = hp.quantile(0.99)
        r["cagr_ex_top1pct"] = bt.cagr(bt.simulate(sel[hp < cut], paths, bench, H=H, start=start, end=end)[0])
    r["spy"] = bt.bench_cagr(bench, eq.index[0], eq.index[-1], "SPY")
    r["iwm"] = bt.bench_cagr(bench, eq.index[0], eq.index[-1], "IWM")
    r["mean_hpr"] = float(sel[f"hpr{H}"].mean()); r["median_hpr"] = float(sel[f"hpr{H}"].median())
    r["window"] = f"{eq.index[0].date()}..{eq.index[-1].date()}"
    return r, eq


def event_excess(ev, bench, H):
    """event-level excess over IWM for the same entry/exit dates"""
    cal = bench.index; iwm = bench.IWM.values; spy = bench.SPY.values
    ei = ev.ent_ci.astype(int).values; xi = np.minimum(ei + H, len(cal) - 1)
    return ev[f"hpr{H}"].values - (iwm[xi] / iwm[ei] - 1), ev[f"hpr{H}"].values - (spy[xi] / spy[ei] - 1)


def fmt(df):
    df = df.copy()
    for c in df.columns:
        if c.startswith("cagr") or c in ("spy", "iwm", "maxdd", "mean_hpr", "median_hpr", "miss_frac"):
            df[c] = (100 * df[c]).round(1)
    if "avg_pos" in df:
        df["avg_pos"] = df.avg_pos.round(0)
    return df


def main(mode):
    ev, paths, bench = get_prepared()
    if mode == "prep":
        print(ev.status.value_counts()); return
    if mode == "dev":
        per = (ev.fdate >= "2006-01-01") & (ev.fdate <= "2015-12-31")
        end = None
        # portfolio window: first trading day of 2006 .. last exit of a dev event
        last_exit = bench.index[min(len(bench) - 1, int(ev[per & (ev.status == "ok")].ent_ci.max()) + 252)]
        start, endd = "2006-01-01", None
        out = f"{HERE}/dev_results"
    else:
        per = ev.fdate >= "2016-01-01"
        start, endd = "2016-01-01", None
        out = f"{HERE}/test_results"
    os.makedirs(out, exist_ok=True)
    evp = ev[per]
    # ------------- coverage -------------
    cov = pd.crosstab(evp.fdate.dt.year, evp.status, margins=True)
    cov["frac_ok"] = (cov.get("ok", 0) / cov["All"]).round(3)
    cov.to_csv(f"{out}/coverage.csv"); print(cov.to_string())
    elig = evp[evp.vwap >= 2]
    print("events with SEC vwap>=$2:", len(elig), " no usable prices:", (elig.status != "ok").mean().round(3))
    if mode == "dev":
        rows = []
        for name in VARIANTS:
            for H in (21, 63, 126, 252):
                if H != 126 and name not in ("base", "opportunistic(n_opp>=3)", "all4(opp+big+ceo/cfo+decline)"):
                    continue
                endH = bench.index[min(len(bench) - 1, int(ev[per & (ev.status == 'ok')].ent_ci.max()) + H)]
                r, eq = run_variant(ev, paths, bench, per, name, H=H, start=start, end=endH)
                rows.append(r); print(fmt(pd.DataFrame([r])).to_string(index=False), flush=True)
        res = pd.DataFrame(rows); fmt(res).to_csv(f"{out}/variants.csv", index=False)
        # halves
        rows = []
        for lab, a, b in [("2006-2010", "2006-01-01", "2010-12-31"), ("2011-2015", "2011-01-01", "2015-12-31")]:
            ph = (ev.fdate >= a) & (ev.fdate <= b)
            for name in VARIANTS:
                endH = bench.index[min(len(bench) - 1, int(ev[ph & (ev.status == 'ok')].ent_ci.max()) + 126)]
                r, _ = run_variant(ev, paths, bench, ph, name, H=126, start=a, end=endH, top_cut=False)
                r["half"] = lab; rows.append(r)
        hv = fmt(pd.DataFrame(rows)); hv.to_csv(f"{out}/halves.csv", index=False)
        print(hv[["half", "variant", "n_events", "cagr", "cagr_2x", "cagr_miss-50", "spy", "iwm"]].to_string(index=False))
    return ev, paths, bench


if __name__ == "__main__":
    main(sys.argv[1])
