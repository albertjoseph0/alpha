"""Event returns and price features. Entry = first open strictly after acceptance (acceptance before
09:15 ET on a trading day -> that day's open; else the next trading day's open). Forward returns are
open-to-open over N trading days; abnormal = stock minus SPY over the same window. Price features use
only closes up to the last close before acceptance."""
import numpy as np, pandas as pd
from common import DATA, M06

ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate", "accept_et"])
px = pd.read_parquet(M06 / "prices.parquet")
O = px.pivot(index="date", columns="ticker", values="Open")
C = px.pivot(index="date", columns="ticker", values="Close")
V = px.pivot(index="date", columns="ticker", values="Volume")
dates = O.index
ev["tk"] = ev.ticker.str.replace(".", "-", regex=False)
H = [5, 10, 20, 40, 60]
rows = []
for r in ev.itertuples():
    a = r.accept_et
    d0 = a.normalize()
    i = dates.searchsorted(d0)  # first trading date >= acceptance day
    if i < len(dates) and dates[i] == d0 and a.hour * 60 + a.minute >= 9 * 60 + 15:
        i += 1
    rec = {"acc": r.accessionNumber, "entry_idx": i}
    if r.tk not in O.columns or i >= len(dates) or i < 3:
        rows.append(rec); continue
    o, c, v = O[r.tk].values, C[r.tk].values, V[r.tk].values
    so, sc = O["SPY"].values, C["SPY"].values
    rec["entry_date"] = dates[i]
    rec["entry_open"] = o[i]
    for h in H:
        j = i + h
        if j < len(dates) and np.isfinite(o[i]) and np.isfinite(o[j]):
            rec[f"r{h}"] = o[j] / o[i] - 1
            rec[f"s{h}"] = so[j] / so[i] - 1
            rec[f"ar{h}"] = rec[f"r{h}"] - rec[f"s{h}"]
    p = i - 1  # last close before entry open (= before acceptance for after-hours; see note in README)
    # for intraday filings (accepted 09:15-16:00) the close of the acceptance day is after acceptance,
    # so use the prior day's close as the last "pre-event" close
    if a.normalize() == dates[p] and a.hour * 60 + a.minute < 16 * 60:
        p -= 1
    rec["pre_close_idx"] = p
    cl = c[:p + 1]
    lb = lambda k: cl[-1] / cl[-k - 1] - 1 if p >= k else np.nan
    rec["ret5"], rec["ret21"], rec["ret63"] = lb(5), lb(21), lb(63)
    rec["sret21"] = sc[p] / sc[p - 21] - 1 if p >= 21 else np.nan
    k = min(63, p)
    lr = np.diff(np.log(cl[-k - 1:]))
    rec["vol63"] = np.nanstd(lr) * np.sqrt(252) if k >= 15 else np.nan
    rec["dvol63"] = np.log(np.nanmean(cl[-k:] * v[p - k + 1:p + 1]) + 1)
    rec["hi252"] = cl[-1] / np.nanmax(cl[-252:]) - 1
    rec["gap"] = o[i] / c[p] - 1  # known only at the entry open (not usable as a same-open signal)
    rows.append(rec)
R = pd.DataFrame(rows)
R.to_parquet(DATA / "event_returns.parquet")
print(R.describe().T.to_string())
print("no price:", R.entry_date.isna().sum(), "of", len(R))
