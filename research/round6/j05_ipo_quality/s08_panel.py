"""Event panel: one row per eligible IPO with features (a) numeric, (b) keyword, (c) Jev, and outcomes.
Timing: bar 0 = first trading day. Signal at close of bar ENTRY_BAR-1 (=25), buy at open of bar ENTRY_BAR (26),
sell at open of bar ENTRY_BAR+HOLD (278). Output: panel.parquet"""
import json
import numpy as np, pandas as pd
from common import DATA

ENTRY_BAR, HOLD = 26, 252
m = pd.read_csv(DATA / "meta.csv", parse_dates=["date"])
m = m[m.ipo_text & ~m.blank_check & ~m.units & ~(m.offer_price < 5)].copy()
pm = pd.read_csv(DATA / "price_map.csv")
m = m.merge(pm[["acc", "status", "ticker_used"]], on="acc", how="left")
es = pd.read_csv(DATA / "edgar_status.csv", parse_dates=["last_periodic", "last_6k", "first_25", "first_15", "first_merger"]) \
    if (DATA / "edgar_status.csv").exists() else pd.DataFrame(columns=["acc"])
m = m.merge(es.drop(columns=["cik"], errors="ignore"), on="acc", how="left")
b = pd.read_parquet(DATA / "bench.parquet").ffill()
cal = b.index

# hot market: eligible IPOs in the prior 90 days
d = m.date.values
m["hot90"] = [((d < x) & (d >= x - np.timedelta64(90, "D"))).sum() for x in d]
idx = pd.read_csv(DATA / "index_rows.csv", parse_dates=["date"])
first_reg = idx[idx.form.isin(["S-1", "F-1"])].groupby("cik").date.min()
m["log_reg_days"] = np.log1p((m.date - m.cik.map(first_reg)).dt.days.clip(lower=0))
m["log_offer"] = np.log(m.offer_price)
m["log_proceeds"] = np.log(m.offer_price * m.shares_offered)
m["nasdaq"] = (m.exchange == "nasdaq").astype(float)
m["f1"] = (m.reg_form == "F-1").astype(float)

rows = []
for r in m.itertuples():
    o = dict(acc=r.acc)
    p = DATA / "prices" / f"{r.acc}.parquet"
    if r.status == "ok" and p.exists():
        px = pd.read_parquet(p)
        px = px[px.index >= px.index[0]]
        o["listing"] = px.index[0]
        o["first_day_ret"] = px.close_unadj.iloc[0] / r.offer_price - 1 if r.offer_price == r.offer_price else np.nan
        if len(px) > ENTRY_BAR:
            o["mom_0_25"] = px.adj.iloc[ENTRY_BAR - 1] / px.adj.iloc[0] - 1
            o["px_signal"] = px.close_unadj.iloc[ENTRY_BAR - 1]
            o["entry"] = px.index[ENTRY_BAR]
            xb = min(ENTRY_BAR + HOLD, len(px) - 1)
            o["exit"] = px.index[xb] if ENTRY_BAR + HOLD < len(px) else pd.NaT
            o["ret"] = px.open.iloc[xb] / px.open.iloc[ENTRY_BAR] - 1 if ENTRY_BAR + HOLD < len(px) else np.nan
            o["n_bars"] = len(px)
        o["has_px"] = True
    else:
        o["has_px"] = False
        i0 = cal.searchsorted(r.date + pd.Timedelta(days=1))
        o["listing"] = cal[min(i0, len(cal) - 1)]
        if i0 + ENTRY_BAR < len(cal):
            o["entry"] = cal[i0 + ENTRY_BAR]
        if i0 + ENTRY_BAR + HOLD < len(cal):
            o["exit"] = cal[i0 + ENTRY_BAR + HOLD]
    rows.append(o)
P = m.merge(pd.DataFrame(rows), on="acc")
for bt in ["SPY", "IWM", "IPO"]:
    s = b[f"{bt}_open"]
    ok = P.entry.notna() & P.exit.notna()
    P.loc[ok, f"ret_{bt}"] = s.reindex(P.loc[ok, "exit"]).values / s.reindex(P.loc[ok, "entry"]).values - 1
P["xs_spy"] = P.ret - P.ret_SPY
P["y"] = (P.xs_spy > 0).astype(float).where(P.ret.notna())

# issuer life-cycle: end-of-trading estimate and whether it falls before the exit
far = pd.Timestamp("2100-01-01")
lp_end = P.last_periodic + pd.to_timedelta(np.where(P.f1 == 1, 400, 200), unit="D")
lp_end = lp_end.where(P.last_periodic < pd.Timestamp("2025-06-30"), far)
lp_end = lp_end.where(P.last_periodic.notna() | P.last_6k.notna(), P.date + pd.Timedelta(days=200))
P["end_est"] = pd.concat([P.first_25.fillna(far), P.first_15.fillna(far), lp_end.fillna(far)], axis=1).min(axis=1)
P["acquired"] = (P.first_merger.notna() & (P.end_est < far) & (P.first_merger <= P.end_est + pd.Timedelta(days=60))
                 & (P.first_merger >= P.end_est - pd.Timedelta(days=400)))
P["dies_in_hold"] = (P.end_est <= P.exit.fillna(far)) & ~P.has_px   # priced names: series runs to today

# Jev answers
for q in ["v1"]:
    f = DATA / f"jev_{q}.jsonl"
    if not f.exists():
        continue
    J = []
    for l in open(f):
        j = json.loads(l); a = j["ans"]; o = {"acc": j["acc"]}
        for k, v in a.items():
            if v.get("type") == "noul" or "noul" in v:
                o[f"j_{k}"] = v["noul"]
            elif "score" in v:
                o[f"j_{k}"] = v["score"]
            elif "probabilities" in v:
                for c, pv in v["probabilities"].items():
                    o[f"j_{k}_{c}"] = pv
        J.append(o)
    P = P.merge(pd.DataFrame(J), on="acc", how="left")
P["year"] = P.date.dt.year
P.to_parquet(DATA / "panel.parquet")
print(len(P), P.groupby("year").agg(n=("acc", "size"), has_px=("has_px", "mean"), ret=("ret", "mean"),
                                     xs=("xs_spy", "mean"), dies=("dies_in_hold", "mean"), acq=("acquired", "mean")).round(3))
