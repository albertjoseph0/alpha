"""Point-in-time universe: S&P 500 (m11, month-end 2011-12..) + S&P 400 (m01, month-end 2012..), read-only inputs.
Maps tickers to CIK via SEC company_tickers.json (m06 copy) + m06 ticker_cik.csv.
Output DATA/universe.parquet: month_end, ticker, idx (500/400), cik, has_px.
A filing on date d counts as a universe event if the firm was a member at the last month-end before d."""
import json
from common import *

a = pd.read_csv(M11 / "sp500_membership_monthly.csv").assign(idx=500)
b = pd.read_csv(M01 / "membership_monthly.csv").assign(idx=400)
U = pd.concat([a, b]).sort_values("idx", ascending=False).drop_duplicates(["month_end", "ticker"])
U["month_end"] = pd.to_datetime(U.month_end)

j = json.load(open(M06 / "company_tickers.json"))
t2c = {}
for v in j.values():
    t2c.setdefault(v["ticker"].replace(".", "-").upper(), int(v["cik_str"]))
names = {int(v["cik_str"]): v["title"] for v in j.values()}
m6 = pd.read_csv(M06 / "ticker_cik.csv").dropna(subset=["cik"])
for r in m6.itertuples():
    t2c.setdefault(r.ticker, int(r.cik))
U["cik"] = U.ticker.map(t2c)
C = pd.read_pickle(M11 / "close.pkl")
have = set(C.columns[C.notna().any()])
U["has_px"] = U.ticker.isin(have)
U.to_parquet(DATA / "universe.parquet", index=False)
pd.Series(names).rename("name").rename_axis("cik").reset_index().to_parquet(DATA / "cik_names.parquet", index=False)

g = U.groupby(U.month_end.dt.year).agg(n=("ticker", "size"), cik=("cik", lambda s: s.notna().mean()),
                                       px=("has_px", "mean"))
print(g.to_string())
print("tickers", U.ticker.nunique(), "ciks", U.cik.nunique(), "priced tickers without cik",
      sorted(set(U[U.has_px & U.cik.isna()].ticker))[:40])
