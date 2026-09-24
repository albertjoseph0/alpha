"""Insider-cluster backtest library.

prepare()  -> per-event table with the matched price series, pre-entry features and path returns
simulate() -> calendar-time portfolio (equal weight at entry, then drift; fully invested whenever
              >=1 position is open, cash at 0% otherwise) with per-event costs.

Timing: an event is known at the close of its FILING date F at the earliest (EDGAR accepts until
22:00 ET; filings after 17:30 are dated the next business day). We enter at the CLOSE of the first
trading day strictly after F. All filters use data up to and including the close of F.
"""
import os, json, glob, hashlib
import numpy as np, pandas as pd

D = "/home/user/alpha/data/round5/m05_insider_clusters"

# ---------------- cost model (ROUND TRIP, spread + slippage + commission) ----------------
#   price < $5                                   : 300 bp
#   micro  (mcap < $300M, or ADV60 < $1M)        : 200 bp
#   small  ($300M-$2B,    or ADV60 $1M-$10M)     :  80 bp
#   mid    ($2B-$10B,     or ADV60 > $10M)       :  30 bp
# the WORSE of the market-cap bucket (when SEC shares-outstanding known) and the ADV bucket applies.
def cost_rt(price, mcap, adv):
    if price < 5:
        return 0.03
    b_adv = 0 if adv < 1e6 else (1 if adv < 1e7 else 2)
    b_cap = 2 if not np.isfinite(mcap) else (0 if mcap < 3e8 else (1 if mcap < 2e9 else 2))
    return [0.02, 0.008, 0.003][min(b_adv, b_cap)]


def _load_prices():
    px = {}
    for f in glob.glob(f"{D}/px/*.parquet"):
        px[os.path.basename(f)[:-8]] = pd.read_parquet(f)
    sp = {}
    for f in glob.glob(f"{D}/splits/*.parquet"):
        sp[os.path.basename(f)[:-8]] = pd.read_parquet(f).ratio
    return px, sp


def load_bench():
    f = f"{D}/bench.parquet"
    if not os.path.exists(f):
        import yfinance as yf
        b = yf.download(["SPY", "IWM"], start="2005-01-01", auto_adjust=False, progress=False)["Adj Close"]
        b.to_parquet(f)
    return pd.read_parquet(f)


def prepare(H_list=(21, 63, 126, 252)):
    ev = pd.read_parquet(f"{D}/events.parquet")
    cand = pd.read_parquet(f"{D}/event_candidates.parquet")
    so = pd.read_parquet(f"{D}/shares_out.parquet"); so["cik"] = so.cik.astype(str)
    so = so.sort_values("end"); so_g = {k: g for k, g in so.groupby("cik")}
    px, sp = _load_prices()
    bench = load_bench(); cal = bench.index
    cmap = cand.groupby("ev").ticker.apply(list).to_dict()
    rows, paths = [], {}
    for i, e in ev.iterrows():
        rec = dict(ev=i, status="no_ticker")
        cands = cmap.get(i, [])
        if cands:
            rec["status"] = "no_yf_data"
        for t in cands:
            x = px.get(t)
            if x is None:
                continue
            s = sp.get(t)
            fac = np.ones(len(x))
            if s is not None:
                for d, r in s.items():
                    fac[x.index < d] *= r
            raw = x.close.values.astype(float) * fac
            m = (x.index >= e.first_tdate - pd.Timedelta(days=3)) & (x.index <= e.fdate)
            if m.sum() == 0:
                if rec["status"] == "no_yf_data":
                    rec["status"] = "no_coverage"
                continue
            ratio = e.vwap / np.median(raw[m])
            if not (0.75 <= ratio <= 1.33):
                rec["status"] = "price_mismatch"; rec["ratio"] = ratio
                continue
            # ---- matched ----
            pre = x.index <= e.fdate
            if pre.sum() < 60:
                rec["status"] = "short_history"; continue
            dv = (x.close.values.astype(float) * x.vol.values.astype(float))[pre][-60:]
            adv = float(np.median(dv))
            p_f = raw[pre][-1]
            adj = x.adj.values.astype(float)
            a_pre = adj[pre]
            ret63 = a_pre[-1] / a_pre[-64] - 1 if len(a_pre) >= 64 else np.nan
            ret126 = a_pre[-1] / a_pre[-127] - 1 if len(a_pre) >= 127 else np.nan
            lr = np.diff(np.log(a_pre[-61:]))
            vol_d = float(np.nanstd(lr))
            g = so_g.get(str(e.cik))
            mcap = np.nan
            if g is not None:
                gg = g[(g.end <= e.fdate) & (g.end >= e.fdate - pd.Timedelta(days=450))]
                if len(gg):
                    mcap = float(gg.shares.iloc[-1]) * p_f
            # entry: first trading day strictly after F, at close; stock must trade within 5 days
            ci = cal.searchsorted(e.fdate, side="right")
            if ci >= len(cal):
                rec["status"] = "after_data_end"; break
            ent_day = cal[ci]
            post = x.index[x.index >= ent_day]
            if len(post) == 0 or (post[0] - ent_day).days > 7:
                rec["status"] = "no_post_data"; break
            ent_ci = cal.searchsorted(post[0])
            aser = x.adj.astype(float).reindex(cal[ent_ci:]).ffill()
            last_real = x.index[-1]
            rec.update(status="ok", ticker=t, price=p_f, adv=adv, mcap=mcap, ret63=ret63,
                       ret126=ret126, vol_d=vol_d, ent_ci=ent_ci, last_real=last_real,
                       cost=cost_rt(p_f, mcap, adv))
            for H in H_list:
                xi = min(ent_ci + H, len(cal) - 1)
                a = aser.values[: xi - ent_ci + 1]
                rec[f"hpr{H}"] = a[-1] / a[0] - 1
                rec[f"trunc{H}"] = bool(last_real < cal[xi] - pd.Timedelta(days=10))
                rec[f"open{H}"] = bool(ent_ci + H > len(cal) - 1)
            paths[i] = aser.values[: min(max(H_list), len(cal) - 1 - ent_ci) + 1]
            # lookahead diagnostics: entry at close of transaction date / filing date
            tdi = x.index.searchsorted(e.first_tdate)
            fdi = x.index.searchsorted(e.fdate, side="right") - 1
            if tdi < len(x) and fdi >= 0:
                a126 = aser.values[min(126, len(aser) - 1)]
                rec["pre_run_t2f"] = adj[fdi] / adj[tdi] - 1          # trans date -> filing date
                rec["pre_run_f2e"] = aser.values[0] / adj[fdi] - 1     # filing date -> entry
            break
        rows.append(rec)
    info = pd.DataFrame(rows).set_index("ev")
    out = ev.join(info)
    return out, paths, bench


def simulate(sel, paths, bench, H=126, start=None, end=None, cost_mult=1.0, missing_ret=None,
             missing=None, extra_cost=None):
    """sel: events with status ok (index -> paths). missing: events without prices to include
    with a synthetic flat path and a terminal return of missing_ret at exit."""
    cal = bench.index
    s_i = cal.searchsorted(pd.Timestamp(start)) if start else 0
    e_i = cal.searchsorted(pd.Timestamp(end), side="right") - 1 if end else len(cal) - 1
    T = e_i - s_i + 1
    ent, ext, ret_paths, cst = [], [], [], []
    for k, r in sel.iterrows():
        p = paths[k]
        ei = int(r.ent_ci)
        if ei < s_i or ei > e_i:
            continue
        xi = min(ei + H, e_i)
        a = p[: xi - ei + 1]
        rr = a[1:] / a[:-1] - 1
        c = r.cost * cost_mult + (0 if extra_cost is None else extra_cost.get(k, 0))
        ent.append(ei - s_i); ext.append(xi - s_i); ret_paths.append(rr); cst.append(c)
    if missing is not None and missing_ret is not None:
        for k, r in missing.iterrows():
            ci = cal.searchsorted(r.fdate, side="right")
            if ci < s_i or ci > e_i:
                continue
            xi = min(ci + H, e_i)
            rr = np.zeros(xi - ci)
            if len(rr) and xi == ci + H:
                rr[-1] = missing_ret
            ent.append(ci - s_i); ext.append(xi - s_i); ret_paths.append(rr); cst.append(0.02 * cost_mult)
    n = len(ent)
    ent = np.array(ent); ext = np.array(ext); cst = np.array(cst)
    by_ent = {}; by_ext = {}
    for j in range(n):
        by_ent.setdefault(ent[j], []).append(j); by_ext.setdefault(ext[j], []).append(j)
    vals = np.zeros(n); active = np.zeros(n, bool)
    cash = 1.0; eq = np.empty(T); nact = np.empty(T, int); turnover = 0.0
    for t in range(T):
        idx = np.nonzero(active)[0]
        for j in idx:
            vals[j] *= 1 + ret_paths[j][t - ent[j] - 1]
        # exits at close t
        for j in by_ext.get(t, []):
            if active[j]:
                cash += vals[j] * (1 - cst[j] / 2); turnover += vals[j]; vals[j] = 0; active[j] = False
        new = [j for j in by_ent.get(t, []) if ext[j] > t]
        if new or by_ext.get(t):
            idx = np.nonzero(active)[0]
            E = vals[idx].sum(); P = cash + E
            nn = len(idx) + len(new)
            if nn > 0:
                target = P / nn
                c_old = (vals[idx] * cst[idx]).sum() / E if E > 0 else 0.0
                want_old = P - target * len(new)
                trade_old = abs(E - want_old)
                cost_old = trade_old * c_old / 2
                cost_new = sum(target * cst[j] / 2 for j in new)
                P_after = P - cost_old - cost_new
                target = P_after / nn
                if E > 0:
                    vals[idx] *= target * len(idx) / E
                for j in new:
                    vals[j] = target; active[j] = True
                turnover += trade_old + target * len(new)
                cash = 0.0
        eq[t] = cash + vals[active].sum(); nact[t] = active.sum()
    dates = cal[s_i:e_i + 1]
    return pd.Series(eq, dates), pd.Series(nact, dates)


def cagr(eq):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1


def maxdd(eq):
    return float((eq / eq.cummax() - 1).min())


def bench_cagr(bench, s, e, col):
    b = bench[col].loc[s:e].dropna()
    return cagr(b)
