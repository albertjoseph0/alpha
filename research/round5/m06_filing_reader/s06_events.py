"""Build the event table: acceptance time -> last pre-news close, first executable open (entry),
untradeable pre-entry reaction and tradeable post-entry returns (stock and SPY), joined with scores.
Usage: s06_events.py SCORES1.parquet [SCORES2.parquet ...]  -> events_scored.parquet"""
import sys
import numpy as np, pandas as pd
from common import DATA

ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate", "accept_et"])
sc = pd.concat([pd.read_parquet(DATA / f) for f in sys.argv[1:]]).drop_duplicates("acc")
ev = ev.merge(sc, left_on="accessionNumber", right_on="acc", how="inner")

px = pd.read_parquet(DATA / "prices.parquet")
O = px.pivot(index="date", columns="ticker", values="Open")
C = px.pivot(index="date", columns="ticker", values="Close")
days = C["SPY"].dropna().index
O, C = O.reindex(days), C.reindex(days)
pos = {d: i for i, d in enumerate(days)}
SAME_DAY_CUTOFF = pd.Timedelta(hours=9, minutes=15)   # accepted by 09:15 ET -> same-day open is executable
CLOSE = pd.Timedelta(hours=16)

recs = []
for r in ev.itertuples():
    t = r.accept_et; d0 = t.normalize(); tod = t - d0
    i0 = days.searchsorted(d0)          # first trading day >= d0
    is_td = i0 < len(days) and days[i0] == d0
    if is_td and tod <= SAME_DAY_CUTOFF:
        ie = i0; ip = i0 - 1
    elif is_td and tod >= CLOSE:
        ie = i0 + 1; ip = i0
    elif is_td:                          # intraday acceptance: react intraday, trade next open
        ie = i0 + 1; ip = i0 - 1
    else:
        ie = i0; ip = i0 - 1
    tk = r.ticker.replace(".", "-")
    rec = {"acc": r.accessionNumber, "ticker": tk, "cik": r.cik, "accept_et": t, "session":
           "pre" if (is_td and tod <= SAME_DAY_CUTOFF) else ("post" if (not is_td or tod >= CLOSE) else "intraday"),
           "entry_date": days[ie] if ie < len(days) else pd.NaT, "has_px": tk in C.columns}
    if ie < len(days) and ip >= 0 and tk in C.columns:
        c, o, s = C[tk].values, O[tk].values, C["SPY"].values; so = O["SPY"].values
        rec["r_pre"] = o[ie] / c[ip] - 1
        rec["spy_pre"] = so[ie] / s[ip] - 1
        for N in (1, 5, 20):
            j = ie + N - 1
            if j < len(days):
                # delisted mid-hold: exit at last available close
                cc = c[ie:j + 1]; last = cc[~np.isnan(cc)][-1] if (~np.isnan(cc)).any() else np.nan
                rec[f"r_{N}"] = last / o[ie] - 1
                rec[f"spy_{N}"] = s[j] / so[ie] - 1
                # close-entry variant (enter at entry-day close, hold N days)
                if j + 1 < len(days):
                    cc2 = c[ie:j + 2]; l2 = cc2[~np.isnan(cc2)][-1] if (~np.isnan(cc2)).any() else np.nan
                    rec[f"rc_{N}"] = l2 / c[ie] - 1
                    rec[f"spyc_{N}"] = s[j + 1] / s[ie] - 1
        rec["r_day0"] = c[ie] / c[ip] - 1   # "announcement-day" close-to-close return (untradeable part + open->close)
    recs.append(rec)
E = pd.DataFrame(recs)
E = E.merge(ev[["accessionNumber", "filingDate", "company", "dtype", "nchar", "nsent", "fb_mean", "fb_head", "fb_pos",
                "fb_neg", "fb_frac_neg", "lm_pos", "lm_neg", "lm_tone"]], left_on="acc", right_on="accessionNumber").drop(columns="accessionNumber")
E = E.sort_values("accept_et").reset_index(drop=True)
# tone change vs the same firm's previous release (within 200 days)
for s in ["fb_mean", "fb_head", "lm_tone"]:
    prev = E.groupby("cik")[s].shift(1); pt = E.groupby("cik")["accept_et"].shift(1)
    E[s + "_chg"] = np.where((E.accept_et - pt).dt.days <= 200, E[s] - prev, np.nan)
for N in (1, 5, 20):
    E[f"ar_{N}"] = E[f"r_{N}"] - E[f"spy_{N}"]
    E[f"arc_{N}"] = E[f"rc_{N}"] - E[f"spyc_{N}"]
E["ar_pre"] = E.r_pre - E.spy_pre
E.to_parquet(DATA / "events_scored.parquet")
print(len(E), "events;", E.has_px.mean().round(3), "with prices;", E.session.value_counts().to_dict())
