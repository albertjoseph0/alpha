"""Build the event table (one row per subject company per 182-day window) from filings.csv + prices.

Event   = all initial 13Ds on one subject CIK on one file_date; a later initial 13D on the same subject within
          182 days of a kept event is dropped (no double counting of the same campaign).
Entry   = close of the first trading day strictly after file_date (EDGAR assigns filings accepted after
          17:30 ET to the next business day, so the filing is public before that close).
Pre-filing features use prices up to and including the file_date close (t-1 relative to entry).
Investable = raw (split-unadjusted) price >= $2 on file_date and 20-day median dollar volume >= $250k.
Forward returns r{H} = close[entry+H]/close[entry]-1 (ticker series forward-filled), same for SPY and IWM.

Output: data/orch/o01_activist_13d/events.parquet (all events, incl. those without ticker/prices).
"""
import numpy as np
import pandas as pd

from common import D, cost_oneway, load_close

HS = (21, 63, 126, 252)
INIT = ("SC 13D", "SCHEDULE 13D")


def filer_history(ev: pd.DataFrame) -> pd.DataFrame:
    h = pd.read_parquet(D / "all_hits.parquet")
    h["fd"] = pd.to_datetime(h["file_date"])
    h["filers"] = h["ciks"].str.split("|").str[1:]
    x = h[["fd", "form", "filers"]].explode("filers").dropna()
    out = {}
    for name, sub in (("n_init_365", x[x["form"].isin(INIT)]), ("n_all_365", x)):
        idx = {k: np.sort(v.to_numpy()) for k, v in sub.groupby("filers")["fd"]}
        vals = []
        for fd, fc in zip(ev["file_date"], ev["filer_ciks"]):
            lo, best = fd - pd.Timedelta(days=365), 0
            for c in str(fc).split("|"):
                a = idx.get(c)
                if a is not None:
                    best = max(best, int(np.searchsorted(a, np.datetime64(fd), "left") - np.searchsorted(a, np.datetime64(lo), "left")))
            vals.append(best)
        out[name] = vals
    return pd.DataFrame(out, index=ev.index)


def main():
    f = pd.read_csv(D / "filings.csv", dtype=str)
    f["file_date"] = pd.to_datetime(f["file_date"])
    f = f[f["file_date"] >= "2014-01-01"].copy()
    f["tk"] = f["ticker"].str.replace(".", "-", regex=False)
    f["filer_ciks"] = f["ciks"].str.split("|").str[1:].str.join("|")
    f["sic0"] = f["sics"].fillna("").str.split("|").str[0]
    g = (f.sort_values(["subject_cik", "file_date", "adsh"])
         .groupby(["subject_cik", "file_date"], as_index=False)
         .agg(adsh_list=("adsh", "|".join), n_acc=("adsh", "size"), tk=("tk", "first"),
              subject_name=("subject_name", "first"),
              filer_names=("filer_names", lambda s: " | ".join(dict.fromkeys(" | ".join(s.dropna()).split(" | ")))),
              filer_ciks=("filer_ciks", lambda s: "|".join(dict.fromkeys("|".join(s.dropna()).split("|")))),
              sic0=("sic0", "first")))
    keep, last = [], {}
    for sc, fd in zip(g["subject_cik"], g["file_date"]):
        lt = last.get(sc)
        if lt is None or (fd - lt).days > 182:
            keep.append(True); last[sc] = fd
        else:
            keep.append(False)
    ev = g[np.array(keep)].reset_index(drop=True)
    print("filings", len(f), "subject-days", len(g), "events", len(ev), flush=True)

    close = load_close()
    vol = pd.read_parquet(D / "px_vol.parquet"); vol.index = pd.to_datetime(vol.index)
    vol = vol.reindex(close.index)
    spl = pd.read_parquet(D / "px_split.parquet"); spl["date"] = pd.to_datetime(spl["date"])
    cal = close.index[close["SPY"].notna()]
    close, vol = close.reindex(cal), vol.reindex(cal)
    T = len(cal)
    spy, iwm = close["SPY"].to_numpy(), close["IWM"].to_numpy()

    ev["has_tk"] = ev["tk"].notna()
    ev["priced"] = ev["tk"].isin(close.columns)
    cols = {k: np.full(len(ev), np.nan) for k in
            ["raw_px", "adv20", "ret_m20", "ret_m126", "vol60", "ret_fd", "react"]
            + [f"{p}{h}" for h in HS for p in ("r", "spy", "iwm")]}
    trunc = {h: np.zeros(len(ev), bool) for h in HS}
    entry = [pd.NaT] * len(ev)
    for i, r in ev[ev["priced"]].iterrows():
        c = close[r["tk"]].ffill(limit=5).to_numpy()
        v = vol[r["tk"]].to_numpy()
        p0 = cal.searchsorted(r["file_date"], "right") - 1
        if p0 < 130 or p0 + 1 >= T:
            continue
        ei = p0 + 1
        while ei < min(p0 + 6, T) and np.isnan(c[ei]):
            ei += 1
        if ei >= T or np.isnan(c[ei]) or np.isnan(c[p0]):
            continue
        entry[i] = cal[ei]
        s = spl[(spl["tk"] == r["tk"]) & (spl["date"] > cal[p0])]["split"].prod()
        cols["raw_px"][i] = c[p0] * (s if s > 0 else 1.0)
        dv = (c[p0 - 19:p0 + 1] * np.nan_to_num(v[p0 - 19:p0 + 1]))
        cols["adv20"][i] = np.nanmedian(dv)
        cols["ret_m20"][i] = c[p0] / c[p0 - 20] - 1
        cols["ret_m126"][i] = c[p0] / c[p0 - 126] - 1
        dr = np.diff(c[p0 - 60:p0 + 1]) / c[p0 - 60:p0]
        cols["vol60"][i] = np.nanstd(dr) * np.sqrt(252)
        cols["ret_fd"][i] = c[p0] / c[p0 - 1] - 1
        cols["react"][i] = c[ei] / c[p0] - 1
        lastv = np.where(~np.isnan(c))[0].max()
        for h in HS:
            if ei + h <= T - 1:
                xi = min(ei + h, lastv)
                trunc[h][i] = xi < ei + h
                cols[f"r{h}"][i] = c[xi] / c[ei] - 1
                cols[f"spy{h}"][i] = spy[xi] / spy[ei] - 1
                cols[f"iwm{h}"][i] = iwm[xi] / iwm[ei] - 1
    for k, v in cols.items():
        ev[k] = v
    for h in HS:
        ev[f"trunc{h}"] = trunc[h]
    ev["entry_date"] = pd.to_datetime(pd.Series(entry, index=ev.index))
    ev["investable"] = (ev["raw_px"] >= 2) & (ev["adv20"] >= 250e3)
    ev["cost1"] = cost_oneway(ev["adv20"].fillna(0), ev["raw_px"].fillna(0))
    ev = pd.concat([ev, filer_history(ev)], axis=1)
    ev["year"] = ev["file_date"].dt.year
    ev.to_parquet(D / "events.parquet")
    acc = ev.groupby("year").agg(events=("subject_cik", "size"), has_tk=("has_tk", "sum"), priced=("priced", "sum"),
                                 entry=("entry_date", "count"), investable=("investable", "sum"))
    print(acc.to_string())
    acc.to_csv(D / "survivorship_counts.csv")


if __name__ == "__main__":
    main()
