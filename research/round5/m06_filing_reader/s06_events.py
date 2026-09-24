"""Build the event table: acceptance time -> last pre-news close (ip), first executable open (ie, entry),
price features known by the entry-day close, and forward returns from the entry open (stock and SPY),
joined with FinBERT/LM scores (sc_part*.parquet) and Jev features (jev_features.parquet, if present).
Timing: accepted <= 09:15 ET on a trading day -> that day's open; accepted 09:15-16:00 -> next open
(intraday reaction is untradeable and counted in the gap); accepted >= 16:00 or non-trading day -> next open.
Usage: s06_events.py  -> DATA/events_scored.parquet"""
import glob
import numpy as np, pandas as pd
from common import DATA

ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate", "accept_et"])
sc = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(DATA / "sc_part*.parquet")))]).drop_duplicates("acc")
ev = ev.merge(sc, left_on="accessionNumber", right_on="acc", how="inner")

px = pd.read_parquet(DATA / "prices.parquet")
O = px.pivot(index="date", columns="ticker", values="Open")
C = px.pivot(index="date", columns="ticker", values="Close")
days = C["SPY"].dropna().index
O, C = O.reindex(days), C.reindex(days)
SAME_DAY_CUTOFF = pd.Timedelta(hours=9, minutes=15)
CLOSE = pd.Timedelta(hours=16)
s, so = C["SPY"].values, O["SPY"].values
H = (21, 42, 63)

recs = []
for r in ev.itertuples():
    t = r.accept_et; d0 = t.normalize(); tod = t - d0
    i0 = days.searchsorted(d0)
    is_td = i0 < len(days) and days[i0] == d0
    if is_td and tod <= SAME_DAY_CUTOFF:
        ie, ip, sess = i0, i0 - 1, "pre"
    elif is_td and tod >= CLOSE:
        ie, ip, sess = i0 + 1, i0, "post"
    elif is_td:
        ie, ip, sess = i0 + 1, i0 - 1, "intraday"
    else:
        ie, ip, sess = i0, i0 - 1, "nontrading"
    tk = r.ticker.replace(".", "-")
    rec = {"acc": r.accessionNumber, "ticker": tk, "cik": r.cik, "accept_et": t, "session": sess,
           "entry_date": days[ie] if ie < len(days) else pd.NaT, "has_px": tk in C.columns}
    if ie < len(days) and ip >= 252 and tk in C.columns:
        c, o = C[tk].values, O[tk].values
        if np.isfinite(o[ie]) and np.isfinite(c[ip]):
            rec["gap_x"] = (o[ie] / c[ip] - 1) - (so[ie] / s[ip] - 1)
            rec["day0_x"] = (c[ie] / o[ie] - 1) - (s[ie] / so[ie] - 1)
            rec["react_x"] = (c[ie] / c[ip] - 1) - (s[ie] / s[ip] - 1)
            rec["mom_12_1"] = c[ip - 21] / c[ip - 252] - 1
            rec["mom_1m"] = c[ip] / c[ip - 21] - 1
            lr = np.diff(np.log(c[ip - 60:ip + 1]))
            rec["vol60"] = np.nanstd(lr) * np.sqrt(252)
            for N in H:
                j = ie + N - 1
                if j < len(days):
                    cc = c[ie:j + 1]; ok = np.isfinite(cc)
                    last = cc[ok][-1] if ok.any() else np.nan   # delisted mid-hold: exit at last close
                    rec[f"r_{N}"] = last / o[ie] - 1
                    rec[f"spy_{N}"] = s[j] / so[ie] - 1
                    rec[f"end_{N}"] = days[j]
    recs.append(rec)
E = pd.DataFrame(recs)
keep = ["accessionNumber", "filingDate", "company", "dtype", "nchar", "nsent", "fb_mean", "fb_head", "fb_pos",
        "fb_neg", "fb_frac_neg", "lm_pos", "lm_neg", "lm_tone"]
E = E.merge(ev[keep], left_on="acc", right_on="accessionNumber").drop(columns="accessionNumber")
E = E.sort_values("accept_et").reset_index(drop=True)
# change vs the same firm's previous release (20..200 days earlier)
pt = E.groupby("cik")["accept_et"].shift(1)
E["has_prev"] = ((E.accept_et - pt).dt.days.between(20, 200)).astype(float)
for c_ in ["fb_mean", "fb_head", "fb_neg", "lm_tone", "lm_neg", "lm_pos"]:
    prev = E.groupby("cik")[c_].shift(1)
    E[c_ + "_chg"] = np.where(E.has_prev == 1, E[c_] - prev, np.nan)
for N in H:
    E[f"ar_{N}"] = E[f"r_{N}"] - E[f"spy_{N}"]
jfs = sorted(glob.glob(str(DATA / "jev_features*.parquet")))   # base run + dated sample runs
if jfs:
    J = pd.concat([pd.read_parquet(f) for f in jfs], ignore_index=True)
    J = J.sort_values("jev_ok").drop_duplicates("acc", keep="last")   # prefer a successful answer
    E = E.merge(J, on="acc", how="left")
    E["jev_ok"] = E.jev_ok.fillna(False).astype(bool)
E.to_parquet(DATA / "events_scored.parquet")
print(len(E), "events;", round(E.has_px.mean(), 3), "with prices;", E.session.value_counts().to_dict())
