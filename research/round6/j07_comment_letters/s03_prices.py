"""Price panel for the PIT S&P 500 universe (m11's yfinance adjusted closes, read-only) and the monthly calendar.
Month m: universe = members at month-end ME (m11), information = letters disseminated on or before ME,
trade at the close of the first trading day after ME (t0), hold to the close of the first trading day of the
next month (t1). Every dissemination is therefore >= 1 trading day before the trade.
Output: DATA/close.parquet (universe tickers + SPY), DATA/months.csv, DATA/member_ret.parquet (month, ticker, ret)."""
from common import *

C = pd.read_pickle(M11 / "close.pkl")
U = pd.read_csv(DATA / "universe_monthly.csv", parse_dates=["month_end"])
tick = sorted(set(U.ticker) & set(C.columns[C.notna().any()]))
C = C[tick + ["SPY"]].astype("float32")
C.index = pd.to_datetime(C.index)
C = C[C.index >= "2011-06-01"]
C.to_parquet(DATA / "close.parquet")
cal = C["SPY"].dropna().index
C = C.loc[cal].ffill(limit=25)  # a name delisted mid-month earns its return up to its last close

rows = []
for me in sorted(U.month_end.unique()):
    me = pd.Timestamp(me)
    i0 = cal.searchsorted(me, side="right")
    nxt = (me + pd.offsets.MonthEnd(1))
    i1 = cal.searchsorted(nxt, side="right")
    if i1 >= len(cal):
        break
    rows.append((me, cal[i0], cal[i1]))
M = pd.DataFrame(rows, columns=["month_end", "t0", "t1"])
M.to_csv(DATA / "months.csv", index=False)

R = []
for r in M.itertuples():
    mem = U[U.month_end == r.month_end].ticker.unique()
    ok = [t for t in mem if t in C.columns]
    p0, p1 = C.loc[r.t0, ok], C.loc[r.t1, ok]
    ret = (p1 / p0 - 1).astype(float)
    R.append(pd.DataFrame({"month_end": r.month_end, "ticker": ok, "ret": ret.values,
                           "p0": p0.values}))
    R.append(pd.DataFrame({"month_end": r.month_end, "ticker": [t for t in mem if t not in C.columns],
                           "ret": np.nan, "p0": np.nan}))
R = pd.concat(R, ignore_index=True)
R["spy"] = R.month_end.map(dict(zip(M.month_end, (C.loc[M.t1, "SPY"].values / C.loc[M.t0, "SPY"].values - 1))))
R.to_parquet(DATA / "member_ret.parquet")
cov = R.groupby("month_end").ret.apply(lambda s: s.notna().mean())
print("months", len(M), M.month_end.min().date(), M.month_end.max().date())
print("price coverage by year:", cov.groupby(cov.index.year).mean().round(3).to_dict())
