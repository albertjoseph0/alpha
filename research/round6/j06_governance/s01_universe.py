"""Season universe + DEF 14A list.

Season Y: S&P 500 PIT members at 30 June Y (m11 monthly rebuild, read-only), CIK from j01's point-in-time
ticker/year map (copied here), and the annual proxy = DEF 14A accepted in (1 July Y-1, 30 June Y].
If several DEF 14As fall in the window, take the latest whose filing size is >= 50% of the largest (annual
proxies are far larger than special-meeting proxies). The portfolio is formed at the close of the first
trading day of July Y, i.e. at least one full session after the latest possible acceptance.

Outputs: DATA/ticker_year_cik.csv (frozen copy), DATA/def14a_all.csv (every DEF 14A of every CIK),
DATA/universe.csv (season x member with cik, acc, accept, primary, has_price)."""
import json
import shutil
from common import *
from sec import get

if not (DATA / "ticker_year_cik.csv").exists():
    shutil.copy(J01 / "ticker_year_cik.csv", DATA / "ticker_year_cik.csv")
TY = pd.read_csv(DATA / "ticker_year_cik.csv")

M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M = M[(M.month_end.dt.month == 6) & M.month_end.dt.year.isin(SEASONS)].copy()
M["season"] = M.month_end.dt.year
M["base"] = M.ticker.str.split("#").str[0]
M = M.merge(TY, left_on=["base", "season"], right_on=["ticker", "year"], how="left", suffixes=("", "_ty"))
M = M.drop(columns=["ticker_ty", "year"])
print("members:", len(M), "no cik:", M.cik.isna().sum())

allf = DATA / "def14a_all.csv"
done = set(pd.read_csv(allf).cik.unique()) if allf.exists() else set()
ciks = sorted(set(M.cik.dropna().astype(int)) - done)
for i, c in enumerate(ciks):
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
    except Exception as e:
        print("fail", c, e, flush=True)
        continue
    blocks = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        if f.get("filingTo", "9999") >= "2012-01-01":
            try:
                blocks.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
            except Exception as e:
                print("fail page", c, f["name"], e, flush=True)
    rows = []
    for b in blocks:
        n = len(b["accessionNumber"])
        for k in range(n):
            if b["form"][k] == "DEF 14A" and b["filingDate"][k] >= "2012-01-01":
                rows.append((c, j.get("name"), b["accessionNumber"][k], b["filingDate"][k],
                             b["acceptanceDateTime"][k], b["primaryDocument"][k], b.get("size", [None] * n)[k]))
    if not rows:
        rows.append((c, j.get("name"), None, None, None, None, None))
    pd.DataFrame(rows, columns=["cik", "name", "acc", "filing_date", "accept", "primary", "size"]).to_csv(
        allf, mode="a", header=not allf.exists(), index=False)
    if i % 100 == 0:
        print(i, c, j.get("name"), len(rows), flush=True)

A = pd.read_csv(allf).dropna(subset=["acc"]).drop_duplicates("acc")
A["accept"] = pd.to_datetime(A.accept.str[:19])
C = load_close()
out = []
for r in M.itertuples():
    rec = dict(season=r.season, ticker=r.ticker, base=r.base, cik=r.cik)
    if pd.notna(r.cik):
        w = A[(A.cik == int(r.cik)) & (A.accept > pd.Timestamp(f"{r.season - 1}-07-01"))
              & (A.accept < pd.Timestamp(f"{r.season}-07-01"))]
        if len(w):
            w = w[w["size"] >= 0.5 * w["size"].max()].sort_values("accept")
            x = w.iloc[-1]
            rec.update(acc=x.acc, accept=x.accept, primary=x.primary, size=x["size"], name=x["name"], n_in_window=len(w))
    fd = C.index[C.index >= pd.Timestamp(f"{r.season}-07-01")][0]
    rec["has_price"] = ("#" not in r.ticker) and (r.ticker in C.columns) and pd.notna(C.at[fd, r.ticker]) if "#" not in r.ticker and r.ticker in C.columns else False
    out.append(rec)
U = pd.DataFrame(out)
U.to_csv(DATA / "universe.csv", index=False)
print(U.groupby("season").agg(n=("ticker", "size"), cik=("cik", "count"), proxy=("acc", "count"),
                              price=("has_price", "sum")).to_string())
print("no proxy examples:", U[U.acc.isna()][["season", "ticker", "cik"]].head(30).to_string())
