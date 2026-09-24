"""Point-in-time S&P 500 month-end membership 2011-12 .. now, rebuilt by walking Wikipedia's change
table backwards from the current list (m06's saved HTML, read-only). Same method as m01's S&P 400
builder. Output: DATA/sp500_membership_monthly.csv (month_end, ticker), DATA/sp500_issues.csv."""
import io
from common import *

cur = pd.read_html(M06 / "sp500_wiki.html")[0]
ch = pd.read_html(M06 / "sp500_hist.html")[0]
ch.columns = ["date", "add_t", "add_n", "rem_t", "rem_n", "reason", "refs"]
ch["date"] = pd.to_datetime(ch["date"].astype(str).str.replace(r"\[.*?\]", "", regex=True).str.strip(),
                            errors="coerce")
bad = ch["date"].isna().sum()
ch = ch.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)

# Ticker renames (old ticker in change log -> ticker under which yfinance keeps the history now).
# Hand-built from the inconsistency log of a first pass.
RENAME = {"FB": "META", "ANTM": "ELV", "HFC": "DINO", "PKI": "RVTY", "FISV": "FI", "WLTW": "WTW",
          "ABC": "COR", "RE": "EG", "FLT": "CPAY", "CDAY": "DAY", "BLL": "BALL", "PEAK": "DOC",
          "ADS": "BFH", "COG": "CTRA", "TMK": "GL", "NLOK": "GEN", "SYMC": "GEN", "HCP": "DOC",
          "KORS": "CPRI", "CBS": "PARA", "VIAC": "PARA", "WYN": "TNL", "DWDP": "DD", "HRS": "LHX",
          "GGP": "GGP", "PCLN": "BKNG", "LUK": "JEF", "UA": "UA", "COV": "COV", "JEC": "J",
          "ESV": "VAL", "PSTG": "P", "GPS": "GAP", "CHK": "EXE", "LB": "BBWI", "FII": "FHI"}
ch["add_t"] = ch["add_t"].map(norm_ticker).map(lambda x: RENAME.get(x, x) if isinstance(x, str) else x)
ch["rem_t"] = ch["rem_t"].map(norm_ticker).map(lambda x: RENAME.get(x, x) if isinstance(x, str) else x)
members = set(cur["Symbol"].map(norm_ticker))
print("current:", len(members), "changes:", len(ch), "unparsed:", bad)

log, snap = [], {}
months = pd.date_range("2011-12-31", pd.Timestamp("2026-09-24"), freq="ME")[::-1]
ci = 0
for me in months:
    while ci < len(ch) and ch.loc[ci, "date"] > me:
        r = ch.loc[ci]
        if isinstance(r.add_t, str):
            ph = [m for m in members if m.startswith(r.add_t + "#")]
            if ph:
                members.discard(ph[0])
            elif r.add_t in members:
                members.discard(r.add_t)
            else:
                log.append((r.date.date(), "added-not-in-set", r.add_t, r.add_n))
        if isinstance(r.rem_t, str):
            if r.rem_t in members:
                log.append((r.date.date(), "removed-already-in-set", r.rem_t, r.rem_n))
                members.add(r.rem_t + "#" + str(r.date.year))
            else:
                members.add(r.rem_t)
        ci += 1
    snap[me] = sorted(members)

rows = [(me.date(), tk) for me, lst in snap.items() for tk in lst]
M = pd.DataFrame(rows, columns=["month_end", "ticker"]).sort_values(["month_end", "ticker"])
M.to_csv(DATA / "sp500_membership_monthly.csv", index=False)
L = pd.DataFrame(log, columns=["date", "issue", "ticker", "name"])
L.to_csv(DATA / "sp500_issues.csv", index=False)
sz = M.groupby("month_end").size()
print(sz.iloc[::12].to_string())
print("issues:", len(L))
print(L.to_string())
print("unique tickers:", M.ticker.nunique())
# sector map for current names (used only for reporting)
cur[["Symbol", "GICS Sector"]].assign(Symbol=cur.Symbol.map(norm_ticker)).to_csv(DATA / "sp500_current_sectors.csv", index=False)
