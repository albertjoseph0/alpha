"""Monthly return panels from m11's adjusted daily closes (read-only).

For each formation month-end t (last trading day of month t):
  sig[t, x]  = close[form_t] / close[form_{t-1}] - 1       (month-t return, known at the close of form_t)
  hold[t, x] = close[t1] / close[t0] - 1                   (t0 = first trading day of t+1, t1 = first of t+2)
so there is a one-day lag between the signal and the entry (entry at the t0 close).
Also benchmark hold returns (SPY, MDY, RSP) over the same windows, and the PIT membership mask.
Output: DATA/panel_sig.parquet, DATA/panel_hold.parquet, DATA/months.csv, DATA/bench_hold.csv, DATA/member_mask.parquet
"""
from common import *

close = pd.read_pickle(M11 / "close.pkl").astype("float64")
bench = pd.read_pickle(M01 / "bench_close.pkl").astype("float64")
idx = close.index
me = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max()     # last trading day per month
fd = pd.Series(idx, index=idx).groupby(idx.to_period("M")).min()     # first trading day per month
per = me.index
rows = []
for i in range(1, len(per) - 2):
    rows.append((per[i], me.iloc[i - 1], me.iloc[i], fd.iloc[i + 1], fd.iloc[i + 2]))
M = pd.DataFrame(rows, columns=["per", "prev_form", "form", "t0", "t1"])
M = M[(M.per >= pd.Period("2011-12", "M"))]
M.to_csv(DATA / "months.csv", index=False)


def ret(px, a, b, ffill_end=False):
    end = px.ffill().reindex(b.values).values if ffill_end else px.reindex(b.values).values
    start = px.reindex(a.values).values
    if ffill_end:  # a name that stops trading inside the holding month exits at its last close
        end = np.where(np.isnan(start), np.nan, end)
    out = end / start - 1
    return pd.DataFrame(out, index=M.form.values, columns=px.columns)


sig = ret(close, M.prev_form, M.form)
hold = ret(close, M.t0, M.t1, ffill_end=True)
sig.index.name = hold.index.name = "form"
sig.to_parquet(DATA / "panel_sig.parquet")
hold.to_parquet(DATA / "panel_hold.parquet")
bh = ret(bench, M.t0, M.t1)
bh.index.name = "form"
bh.to_csv(DATA / "bench_hold.csv")

mem = pd.read_csv(DATA / "members.csv", parse_dates=["month_end"])
mem = mem[mem.has_px]
mem["per"] = mem.month_end.dt.to_period("M")
mm = pd.crosstab(mem.per, mem.ticker).astype(bool)
mm = mm.reindex(M.per.values).fillna(False)
mm.index = M.form.values
mm.index.name = "form"
mm.to_parquet(DATA / "member_mask.parquet")
print(M.head(3).to_string(), M.tail(3).to_string(), sig.shape, hold.shape, mm.shape, sep="\n")
print("hold NaN share among members:", float(np.isnan(hold.where(mm.reindex(columns=hold.columns, fill_value=False)).values[mm.reindex(columns=hold.columns, fill_value=False).values]).mean()))
