"""Point-in-time S&P 500 universe (m11 monthly membership, 2011-12..2026-09, read-only) and a ticker -> CIK map.
CIK sources: (1) insider-transaction data sets (m05, issuer ticker + CIK as reported at the time, point-in-time),
(2) SEC company_tickers.json (current), (3) m06 ticker_cik.csv. Output: DATA/universe_cik.csv."""
import json
from common import *

M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M["base"] = M.ticker.str.split("#").str[0]
yrs = M.groupby("base").month_end.agg(["min", "max"]).reset_index()
print("tickers:", len(yrs))

# (1) insider data: (symbol, year) -> cik counts
rows = []
for f in sorted((M05 / "quarters").glob("20*q?.parquet")):
    y = int(f.name[:4])
    if y < 2011:
        continue
    d = pd.read_parquet(f, columns=["issuercik", "issuertradingsymbol"])
    d["sym"] = d.issuertradingsymbol.map(norm_ticker)
    d = d.dropna(subset=["sym"])
    g = d.groupby(["sym", "issuercik"]).size().reset_index(name="n")
    g["year"] = y
    rows.append(g)
ins = pd.concat(rows)
ins["cik"] = ins.issuercik.astype(int)
print("insider rows", len(ins))

cur = json.load(open(M05 / "company_tickers.json"))
curmap = {}
for v in cur.values():
    curmap.setdefault(norm_ticker(v["ticker"]), int(v["cik_str"]))
m6 = pd.read_csv(M06 / "ticker_cik.csv").dropna(subset=["cik"])
m6map = dict(zip(m6.ticker.map(norm_ticker), m6.cik.astype(int)))

# old symbols for renamed tickers (m11 RENAME, reversed), so the insider data can be searched under the old symbol
OLD = {"META": ["FB"], "ELV": ["ANTM"], "DINO": ["HFC"], "RVTY": ["PKI"], "FI": ["FISV"], "WTW": ["WLTW"],
       "COR": ["ABC"], "EG": ["RE"], "CPAY": ["FLT"], "DAY": ["CDAY"], "BALL": ["BLL"], "DOC": ["PEAK", "HCP"],
       "BFH": ["ADS"], "CTRA": ["COG", "XEC"], "GL": ["TMK"], "GEN": ["NLOK", "SYMC"], "LHX": ["HRS"],
       "PARA": ["CBS", "VIAC"], "TNL": ["WYN"], "DD": ["DWDP"], "BKNG": ["PCLN"], "JEF": ["LUK"], "J": ["JEC"],
       "VAL": ["ESV"], "GAP": ["GPS"], "EXE": ["CHK"], "BBWI": ["LB"], "FHI": ["FII"], "CPRI": ["KORS"]}

out = []
for r in yrs.itertuples():
    t = r.base
    y0, y1 = r.min.year, r.max.year
    syms = [t] + OLD.get(t, [])
    s = ins[ins.sym.isin(syms) & ins.year.between(y0, y1)]
    ins_cik = int(s.groupby("cik").n.sum().idxmax()) if len(s) else None
    ins_share = float(s.groupby("cik").n.sum().max() / s.n.sum()) if len(s) else None
    c_cik = curmap.get(t)
    m_cik = m6map.get(t)
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
    out.append((t, r.min.date(), r.max.date(), cik, src, ins_cik, ins_share, c_cik, m_cik))
U = pd.DataFrame(out, columns=["ticker", "first_me", "last_me", "cik", "src", "ins_cik", "ins_share", "cur_cik", "m06_cik"])
U.to_csv(DATA / "universe_cik.csv", index=False)

# per (ticker, year) CIK: the insider-data mode in that year if clear, else the ticker-level CIK
ty = M.assign(year=M.month_end.dt.year)[["base", "year"]].drop_duplicates()
base = dict(zip(U.ticker, U.cik))
res = []
for r in ty.itertuples():
    syms = [r.base] + OLD.get(r.base, [])
    s = ins[ins.sym.isin(syms) & (ins.year == r.year)]
    c = base.get(r.base)
    if len(s):
        g = s.groupby("cik").n.sum()
        if g.max() / g.sum() >= 0.6:
            c = int(g.idxmax())
    res.append((r.base, r.year, c))
TY = pd.DataFrame(res, columns=["ticker", "year", "cik"]).dropna()
TY["cik"] = TY.cik.astype(int)
TY.to_csv(DATA / "ticker_year_cik.csv", index=False)
multi = TY.groupby("ticker").cik.nunique()
print("tickers with >1 CIK over time:", multi[multi > 1].index.tolist())
print("unique CIKs:", TY.cik.nunique())
print(U.src.value_counts())
dis = U[(U.cur_cik.notna()) & (U.cik.notna()) & (U.cur_cik != U.cik)]
print("insider vs current disagreements:\n", dis.to_string())
print("no cik:", U[U.cik.isna()].ticker.tolist())
