"""Point-in-time universe = S&P 500 (m11 monthly, 2011-12..) UNION S&P 400 (m01 monthly, 2011-12..), read-only.
Ticker -> CIK per (ticker, year): j01's map for S&P 500 names (read-only); the same method for S&P 400 names
(insider-transaction data sets from m05 = issuer symbol + CIK as reported at the time; fallback SEC current map,
then m06). Price availability from m11's close.pkl (S&P 400 panel of m01 + S&P 500 names).
Output: DATA/universe_monthly.parquet (month_end, ticker, idx, cik, has_px)."""
import json
from common import *

M5 = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M5["idx"] = 500
M4 = pd.read_csv(M01 / "membership_monthly.csv", parse_dates=["month_end"])
M4["idx"] = 400
M = pd.concat([M5, M4])
M["base"] = M.ticker.str.split("#").str[0].map(norm_ticker)
M = M.sort_values("idx", ascending=False).drop_duplicates(["month_end", "base"])  # if in both (transition), call it 500
M["year"] = M.month_end.dt.year
print("member-months", len(M), "tickers", M.base.nunique())

TY = pd.read_csv(J01 / "ticker_year_cik.csv")   # S&P 500 (ticker, year) -> cik
have = set(zip(TY.ticker, TY.year))
need = M[["base", "year"]].drop_duplicates()
need = need[[(a, b) not in have for a, b in zip(need.base, need.year)]]
print("(ticker, year) pairs needing a CIK:", len(need), "tickers", need.base.nunique())

rows = []
for f in sorted((M05 / "quarters").glob("20*q?.parquet")):
    y = int(f.name[:4])
    if y < 2011:
        continue
    d = pd.read_parquet(f, columns=["issuercik", "issuertradingsymbol"])
    d["sym"] = d.issuertradingsymbol.map(norm_ticker)
    d = d.dropna(subset=["sym"])
    d = d[d.sym.isin(set(need.base))]
    g = d.groupby(["sym", "issuercik"]).size().reset_index(name="n")
    g["year"] = y
    rows.append(g)
ins = pd.concat(rows)
ins["cik"] = ins.issuercik.astype(int)
cur = json.load(open(M05 / "company_tickers.json"))
curmap = {}
for v in cur.values():
    curmap.setdefault(norm_ticker(v["ticker"]), int(v["cik_str"]))
m6 = pd.read_csv(M06 / "ticker_cik.csv").dropna(subset=["cik"])
m6map = dict(zip(m6.ticker.map(norm_ticker), m6.cik.astype(int)))

# ticker-level fallback: insider mode over the ticker's member years
yrs = need.groupby("base").year.agg(["min", "max"])
tick_cik = {}
for t, r in yrs.iterrows():
    s = ins[(ins.sym == t) & ins.year.between(r["min"], r["max"])]
    g = s.groupby("cik").n.sum()
    if len(g) and g.max() / g.sum() >= 0.6:
        tick_cik[t] = int(g.idxmax())
    elif t in curmap:
        tick_cik[t] = curmap[t]
    elif t in m6map:
        tick_cik[t] = m6map[t]
    elif len(g):
        tick_cik[t] = int(g.idxmax())
res = []
for r in need.itertuples():
    s = ins[(ins.sym == r.base) & (ins.year == r.year)]
    c = tick_cik.get(r.base)
    g = s.groupby("cik").n.sum()
    if len(g) and g.max() / g.sum() >= 0.6:
        c = int(g.idxmax())
    res.append((r.base, r.year, c))
TY4 = pd.DataFrame(res, columns=["ticker", "year", "cik"])
print("S&P 400 pairs without CIK:", TY4.cik.isna().sum(), TY4[TY4.cik.isna()].ticker.unique()[:40])
TYall = pd.concat([TY, TY4.dropna()])
TYall["cik"] = TYall.cik.astype(int)
M = M.merge(TYall.rename(columns={"ticker": "base"}), on=["base", "year"], how="left")

C = pd.read_pickle(M11 / "close.pkl")
Cm = C.resample("ME").last()
Cm.index = Cm.index.normalize()
avail = Cm.notna()
cols = set(C.columns)
M["has_px"] = [bool(b in cols and me in avail.index and avail.at[me, b]) for b, me in zip(M.base, M.month_end)]
U = M[["month_end", "base", "idx", "cik", "has_px"]].rename(columns={"base": "ticker"})
U.to_parquet(DATA / "universe_monthly.parquet", index=False)
s = U.groupby("month_end").agg(n=("ticker", "size"), cik=("cik", lambda x: x.notna().mean()), px=("has_px", "mean"))
print(s.iloc[::12].to_string())
print("unique CIKs:", U.cik.nunique())
