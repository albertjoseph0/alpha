"""Event price features (set a) and labels, from m11's yfinance close/volume panel (read-only).
Acceptance time (UTC) -> ET date; d0 = last trading day <= acceptance date; entry = next trading day's close (d0+1).
Features use closes up to d0. Labels: excess return vs SPY from entry close over 21 / 63 trading days.
Output: DATA/events.parquet (pairs + features + labels)."""
from common import *

C = pd.read_pickle(M11 / "close.pkl").astype("float64")
V = pd.read_pickle(M11 / "volume.pkl").astype("float64")
C = C.loc["2011-01-01":]
V = V.loc[C.index]
dates = C.index
R = C.pct_change(fill_method=None)
P = pd.read_parquet(DATA / "pairs.parquet")
acc = pd.to_datetime(P.accept, utc=True).dt.tz_convert("America/New_York")
P["accept_et"] = acc.dt.tz_localize(None)
P["d0_idx"] = dates.searchsorted(P.accept_et.dt.normalize(), side="right") - 1
P["entry_idx"] = P.d0_idx + 1
spy = C["SPY"]
cols = {c: i for i, c in enumerate(C.columns)}
Cv, Vv, Rv = C.values, V.values, R.values
sp = spy.values
out = []
for r in P.itertuples():
    j = cols.get(r.ticker)
    i0, ie = r.d0_idx, r.entry_idx
    f = {"has_px": 0}
    if j is not None and i0 >= 260 and ie < len(dates):
        c = Cv[:, j]
        if np.isfinite(c[i0]) and np.isfinite(c[ie]):
            f["has_px"] = 1
            f["mom12_1"] = c[i0 - 21] / c[i0 - 252] - 1 if np.isfinite(c[i0 - 252]) else np.nan
            f["mom1"] = c[i0] / c[i0 - 21] - 1
            f["vol60"] = np.nanstd(Rv[i0 - 59:i0 + 1, j]) * np.sqrt(252)
            f["size_dv"] = np.log1p(np.nanmean(c[i0 - 59:i0 + 1] * Vv[i0 - 59:i0 + 1, j]))
            f["ret_d0"] = c[i0] / c[i0 - 1] - 1   # filing-day reaction up to d0 close (known before entry)
            for h in (21, 63, 252):
                k = ie + h
                if k < len(dates):
                    ck = c[k]
                    if not np.isfinite(ck):   # delisted inside the window: last available price
                        seg = c[ie:k + 1]
                        ok = np.where(np.isfinite(seg))[0]
                        ck = seg[ok[-1]]
                        f[f"trunc{h}"] = 1
                    f[f"ret{h}"] = ck / c[ie] - 1
                    f[f"spy{h}"] = sp[k] / sp[ie] - 1
                    f[f"xret{h}"] = f[f"ret{h}"] - f[f"spy{h}"]
    f["entry_date"] = dates[ie] if ie < len(dates) else pd.NaT
    out.append(f)
E = pd.concat([P.reset_index(drop=True), pd.DataFrame(out)], axis=1)
E.to_parquet(DATA / "events.parquet")
print(len(E), "with prices:", E.has_px.sum(), "with 63d label:", E.xret63.notna().sum())
print(E.groupby(pd.to_datetime(E.filing_date).dt.year)[["has_px"]].agg(["size", "mean"]).to_string())
