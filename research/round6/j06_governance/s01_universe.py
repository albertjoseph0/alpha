"""Season universe + DEF 14A list.

Season Y: S&P 500 PIT members at 30 June Y (m11 monthly rebuild, read-only), CIK from j01's point-in-time
ticker/year map (copied here) plus a small manual lineage map for re-domiciled / renamed firms (OVR below),
and candidate proxies = DEF 14A or DEFC14A (contested meetings) of the firm's CIK lineage accepted in
[1 April Y-1, 1 July Y). s02 fetches candidates latest-first and keeps the first one that is an annual-meeting
proxy (has a CD&A and a summary compensation table). The portfolio is formed at the close of the first
trading day of July Y, i.e. at least one full session after the latest possible acceptance.
Share classes of one firm (GOOG/GOOGL, FOX/FOXA, NWS/NWSA, ...) are collapsed to one row per season.

Outputs: DATA/ticker_year_cik.csv (frozen copy), DATA/def14_all.csv (every DEF 14A/DEFC14A of every CIK),
DATA/universe.csv (season x firm with cik lineage, has_price) and DATA/candidates.csv (season x firm x filing)."""
import json
import shutil
from common import *
from sec import get

if not (DATA / "ticker_year_cik.csv").exists():
    shutil.copy(J01 / "ticker_year_cik.csv", DATA / "ticker_year_cik.csv")
TY = pd.read_csv(DATA / "ticker_year_cik.csv")
# lineage CIKs (latest first) for tickers whose PIT map is wrong or whose CIK changed (checked against m05
# insider-data symbols/names); seasons given as (first, last) inclusive.
OVR = {"FOXA": [((2013, 2018), [1308161]), ((2019, 2099), [1754301])],
       "FOX": [((2013, 2018), [1308161]), ((2019, 2099), [1754301])],
       "PSKY": [((2013, 2099), [2041610, 813828])],
       "VTRS": [((2013, 2099), [1792044, 1623613, 69499])],
       "WBA": [((2013, 2099), [1618921, 104207])],
       "LIN": [((2013, 2099), [1707925, 884905])],
       "DOC": [((2013, 2099), [765880])],
       "AVGO": [((2013, 2099), [1730168, 1649338, 1441634])],
       "MDT": [((2013, 2099), [1613103, 64670])],
       "PRGO": [((2013, 2099), [1585364, 820096])],
       "DIS": [((2013, 2099), [1744489, 1001039])],
       "XRX": [((2013, 2099), [1770450, 108772])],
       "APA": [((2013, 2099), [1841666, 6769])],
       "BNY": [((2013, 2099), [1390777])],
       "GOOGL": [((2013, 2099), [1652044, 1288776])],
       "GOOG": [((2013, 2099), [1652044, 1288776])],
       "SW": [((2013, 2015), [1159297]), ((2016, 2018), [1636023]), ((2019, 2024), [1732845, 1636023]),
              ((2025, 2099), [2005951, 1732845])],
       # wrong PIT-map CIKs found by an EDGAR-name vs Wikipedia-name check
       "CTRA": [((2013, 2099), [858470])], "XEC": [((2013, 2099), [1168054])], "COR": [((2013, 2099), [1140859])],
       "EXE": [((2013, 2099), [895126])], "GEN": [((2013, 2099), [849399])], "WTW": [((2013, 2099), [1140536])],
       "PCG": [((2013, 2099), [1004980, 75488])],
       "AGN": [((2013, 2099), [1578845, 884629])], "AGN#2015": [((2013, 2099), [850693])]}
DROP = {"ECHO"}  # m11 artifact (listed in every month; mapped to Echo Global Logistics)


def lineage(tk, season, cik):
    for (a, b), cl in OVR.get(tk, OVR.get(tk.split("#")[0], [])):
        if a <= season <= b:
            return cl
    return [int(cik)] if pd.notna(cik) else []


M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M = M[(M.month_end.dt.month == 6) & M.month_end.dt.year.isin(SEASONS)].copy()
M["season"] = M.month_end.dt.year
M["base"] = M.ticker.str.split("#").str[0]
M = M.merge(TY, left_on=["base", "season"], right_on=["ticker", "year"], how="left", suffixes=("", "_ty"))
M = M.drop(columns=["ticker_ty", "year"])
M = M[~M.base.isin(DROP)].copy()
M["lineage"] = [lineage(t, y, c) for t, y, c in zip(M.ticker, M.season, M.cik)]
M["cik"] = [l[0] if l else np.nan for l in M.lineage]
print("members:", len(M), "no cik:", M.cik.isna().sum())

allf = DATA / "def14_all.csv"
done = set(pd.read_csv(allf).cik.unique()) if allf.exists() else set()
ciks = sorted({c for l in M.lineage for c in l} - done)
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
            if b["form"][k] in ("DEF 14A", "DEFC14A") and b["filingDate"][k] >= "2012-01-01":
                rows.append((c, j.get("name"), b["form"][k], b["accessionNumber"][k], b["filingDate"][k],
                             b["acceptanceDateTime"][k], b["primaryDocument"][k], b.get("size", [None] * n)[k]))
    if not rows:
        rows.append((c, j.get("name"), None, None, None, None, None, None))
    pd.DataFrame(rows, columns=["cik", "name", "form", "acc", "filing_date", "accept", "primary", "size"]).to_csv(
        allf, mode="a", header=not allf.exists(), index=False)
    if i % 100 == 0:
        print(i, c, j.get("name"), len(rows), flush=True)

A = pd.read_csv(allf).dropna(subset=["acc"]).drop_duplicates("acc")
A["accept"] = pd.to_datetime(A.accept.str[:19])
C = load_close()
FD = formation_dates(C.index)
urows, crows = [], []
for r in M.itertuples():
    fd = FD[r.season]
    hp = ("#" not in r.ticker) and (r.ticker in C.columns) and bool(pd.notna(C.at[fd, r.ticker]))
    urows.append(dict(season=r.season, ticker=r.ticker, cik=r.cik, lineage=" ".join(map(str, r.lineage)), has_price=hp))
U = pd.DataFrame(urows)
# collapse share classes: one row per (season, cik); prefer a ticker with a price, then alphabetical
U = U.sort_values(["season", "cik", "has_price", "ticker"], ascending=[True, True, False, True])
dup = U[U.cik.notna() & U.duplicated(["season", "cik"])]
print("share-class duplicates dropped:", sorted(set(dup.ticker)))
U = U[~(U.cik.notna() & U.duplicated(["season", "cik"]))].reset_index(drop=True)
U["fid"] = U.season.astype(str) + "_" + U.ticker.str.replace(r"[^A-Za-z0-9#]", "", regex=True)
for r in U.itertuples():
    if not r.lineage:
        continue
    lin = [int(x) for x in r.lineage.split()]
    w = A[A.cik.isin(lin) & (A.accept >= pd.Timestamp(f"{r.season - 1}-04-01"))
          & (A.accept < pd.Timestamp(f"{r.season}-07-01"))].sort_values("accept", ascending=False)
    for k, x in enumerate(w.itertuples()):
        crows.append(dict(fid=r.fid, season=r.season, ticker=r.ticker, rank=k, cik=x.cik, form=x.form, acc=x.acc,
                          accept=x.accept, primary=x.primary, size=x.size, name=x.name))
U.to_csv(DATA / "universe.csv", index=False)
CD = pd.DataFrame(crows)
CD.to_csv(DATA / "candidates.csv", index=False)
U["n_cand"] = U.fid.map(CD.groupby("fid").size()).fillna(0)
print(U.groupby("season").agg(n=("ticker", "size"), cik=("cik", "count"), has_cand=("n_cand", lambda s: (s > 0).sum()),
                              price=("has_price", "sum")).to_string())
x = U[U.n_cand == 0]
print("no candidate:", len(x))
print(x.groupby("ticker").season.apply(lambda s: ",".join(map(str, s))).to_string())
