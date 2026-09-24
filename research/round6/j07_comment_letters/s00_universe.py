"""Point-in-time S&P 500 universe with CIKs.
Membership: m11's month-end S&P 500 membership 2011-12..2026-09 (rebuilt from Wikipedia's change log, read-only).
CIK: j01's point-in-time (ticker, year) -> CIK map (insider-transaction data sets, then SEC current map; read-only).
Cross-check for 2019-10+: m06's interval file. Output: DATA/universe_monthly.csv (month_end, ticker, cik),
DATA/ticker_year_cik.csv (frozen copy of j01's map)."""
from common import *

M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M["ticker"] = M.ticker.str.split("#").str[0]
TY = pd.read_csv(J01 / "ticker_year_cik.csv")
TY.to_csv(DATA / "ticker_year_cik.csv", index=False)
M["year"] = M.month_end.dt.year
M = M.merge(TY, on=["ticker", "year"], how="left")
print("member-months", len(M), "without CIK", M.cik.isna().sum(), M[M.cik.isna()].ticker.unique()[:30])
M = M.dropna(subset=["cik"])
M["cik"] = M.cik.astype(int)
M[["month_end", "ticker", "cik"]].to_csv(DATA / "universe_monthly.csv", index=False)

# cross-check with m06 intervals (2019-10+)
I = pd.read_csv(M06 / "sp500_pit_intervals.csv", parse_dates=["start", "end"])
chk = M[M.month_end == "2021-06-30"]
inm06 = I[(I.start <= "2021-06-30") & (I.end > "2021-06-30")]
a, b = set(chk.ticker), set(inm06.ticker.map(norm_ticker))
print("2021-06 m11 vs m06 overlap:", len(a & b), "only m11:", sorted(a - b)[:15], "only m06:", sorted(b - a)[:15])
print("unique CIKs:", M.cik.nunique(), "per month:", M.groupby("month_end").size().describe().round(1).to_dict())
