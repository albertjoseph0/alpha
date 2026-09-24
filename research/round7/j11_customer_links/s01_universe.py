"""Supplier universe: point-in-time S&P 500 (m11) U S&P 400 (m01) monthly members, 2011-12..2026-08 (read-only),
restricted to tickers with prices in m11's close.pkl.  Ticker -> CIK via the insider-transaction data sets
(m05, point-in-time symbol+CIK), SEC company_tickers.json (current), m06 ticker_cik.csv (same logic as j01).
Output: DATA/universe.csv (ticker, first_me, last_me, cik, src), DATA/members.csv (month_end, ticker, idx)."""
import json
from common import *

A = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
A["ticker"] = A.ticker.str.split("#").str[0]
A["idx"] = "SP500"
B = pd.read_csv(M01 / "membership_monthly.csv", parse_dates=["month_end"])
B["idx"] = "SP400"
M = pd.concat([A, B]).drop_duplicates(["month_end", "ticker"])
close = pd.read_pickle(M11 / "close.pkl")
M["has_px"] = M.ticker.isin(close.columns)
M.to_csv(DATA / "members.csv", index=False)
g = M.groupby("month_end").agg(n=("ticker", "size"), n_px=("has_px", "sum"))
g["hole"] = 1 - g.n_px / g.n
print(g.iloc[::12].to_string())

yrs = M[M.has_px].groupby("ticker").month_end.agg(["min", "max"]).reset_index()
print("tickers with prices:", len(yrs))

rows = []
for f in sorted((M05 / "quarters").glob("20*q?.parquet")):
    y = int(f.name[:4])
    if y < 2011:
        continue
    d = pd.read_parquet(f, columns=["issuercik", "issuertradingsymbol"])
    d["sym"] = d.issuertradingsymbol.map(norm_ticker)
    d = d.dropna(subset=["sym"])
    gg = d.groupby(["sym", "issuercik"]).size().reset_index(name="n")
    gg["year"] = y
    rows.append(gg)
ins = pd.concat(rows)
ins["cik"] = ins.issuercik.astype(int)
cur = json.load(open(M05 / "company_tickers.json"))
curmap = {}
for v in cur.values():
    curmap.setdefault(norm_ticker(v["ticker"]), int(v["cik_str"]))
m6 = pd.read_csv(M06 / "ticker_cik.csv").dropna(subset=["cik"])
m6map = dict(zip(m6.ticker.map(norm_ticker), m6.cik.astype(int)))
OLD = {"META": ["FB"], "ELV": ["ANTM"], "DINO": ["HFC"], "RVTY": ["PKI"], "FI": ["FISV"], "WTW": ["WLTW"],
       "COR": ["ABC"], "EG": ["RE"], "CPAY": ["FLT"], "DAY": ["CDAY"], "BALL": ["BLL"], "DOC": ["PEAK", "HCP"],
       "BFH": ["ADS"], "CTRA": ["COG", "XEC"], "GL": ["TMK"], "GEN": ["NLOK", "SYMC"], "LHX": ["HRS"],
       "PARA": ["CBS", "VIAC"], "TNL": ["WYN"], "DD": ["DWDP"], "BKNG": ["PCLN"], "JEF": ["LUK"], "J": ["JEC"],
       "VAL": ["ESV"], "GAP": ["GPS"], "EXE": ["CHK"], "BBWI": ["LB"], "FHI": ["FII"], "CPRI": ["KORS"]}
out = []
for r in yrs.itertuples():
    t = r.ticker
    syms = [t] + OLD.get(t, [])
    s = ins[ins.sym.isin(syms) & ins.year.between(r.min.year, r.max.year)]
    ins_cik = int(s.groupby("cik").n.sum().idxmax()) if len(s) else None
    ins_share = float(s.groupby("cik").n.sum().max() / s.n.sum()) if len(s) else None
    c_cik, m_cik = curmap.get(t), m6map.get(t)
    if ins_cik is not None and ins_share >= 0.6:
        cik, src = ins_cik, "insider"
    elif c_cik is not None:
        cik, src = c_cik, "current"
    elif m_cik is not None:
        cik, src = m_cik, "m06"
    elif ins_cik is not None:
        cik, src = ins_cik, "insider_weak"
    else:
        cik, src = None, "none"
    out.append((t, r.min.date(), r.max.date(), cik, src, ins_share, c_cik))
U = pd.DataFrame(out, columns=["ticker", "first_me", "last_me", "cik", "src", "ins_share", "cur_cik"])
U.to_csv(DATA / "universe.csv", index=False)
print(U.src.value_counts())
print("unique CIKs", U.cik.nunique(), "no cik:", U[U.cik.isna()].ticker.tolist())
dup = U.dropna(subset=["cik"]).groupby("cik").ticker.apply(list)
print("CIKs with >1 ticker:", dup[dup.str.len() > 1].to_dict())
