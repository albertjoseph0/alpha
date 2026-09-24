"""Rebuild point-in-time S&P 400 membership (month-end snapshots, 2012-01 .. now) by walking
Wikipedia's constituent-change table backwards from the current list.
Writes data/.../membership_monthly.csv (month_end, ticker) and a log of inconsistencies."""
import io
import re
from common import *

html = open(DATA / "sp400.html").read()
t = pd.read_html(io.StringIO(html))
cur = t[0]
ch = t[1].copy()
ch.columns = ["date", "add_t", "add_n", "rem_t", "rem_n", "reason"]
ch["date"] = pd.to_datetime(ch["date"].astype(str).str.replace(r"\[.*?\]", "", regex=True).str.strip(), errors="coerce")
bad = ch["date"].isna().sum()
ch = ch.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)


def norm(x):
    if not isinstance(x, str) or not x.strip() or x.strip().lower() == "nan":
        return None
    return x.strip().replace(".", "-").upper()


# ticker renames between an addition (old ticker) and the current list / a later removal (new
# ticker). Hand-built from the inconsistency log; yfinance keeps history under the NEW ticker.
RENAME = {"PSTG": "P", "CHK": "EXE", "ZI": "GTM", "HTA": "HR", "UA/UAA": "UAA", "UAA/UA": "UAA",
          "GPS": "GAP", "ELY": "MODG", "HFC": "DINO", "BRKS": "AZTA", "ERI": "CZR", "ADS": "BFH",
          "IIVI": "COHR", "AAXN": "AXON", "CFX": "ENOV", "WTW": "WW", "WWE": "TKO", "WYND": "TNL",
          "APY": "CHX", "SGMS": "LNW", "INCR": "SYNH", "ESV": "VAL", "JCOM": "ZD", "OZRK": "OZK",
          "CSAL": "UNIT", "HYH": "AVNS", "POL": "AVNT", "JDSU": "VIAV", "SAI": "LDOS", "FII": "FHI",
          "DV": "ATGE", "TPX": "SGI", "WXS": "WEX"}
ch["add_t"] = ch["add_t"].map(norm).map(lambda x: RENAME.get(x, x) if isinstance(x, str) else x)
ch["rem_t"] = ch["rem_t"].map(norm).map(lambda x: RENAME.get(x, x) if isinstance(x, str) else x)
members = set(cur["Symbol"].map(norm))
print("current members:", len(members), "changes:", len(ch), "unparsed dates:", bad,
      "range", ch["date"].min().date(), ch["date"].max().date())

log = []
snap = {}
months = pd.date_range("2011-12-31", pd.Timestamp.today().normalize(), freq="ME")[::-1]
ci = 0
for me in months:
    # undo all changes dated after this month end
    while ci < len(ch) and ch.loc[ci, "date"] > me:
        r = ch.loc[ci]
        if isinstance(r.add_t, str):
            ph = [m for m in members if m.startswith(r.add_t + "#")]
            if ph:  # an earlier company that used the same ticker (placeholder, no price data)
                members.discard(ph[0])
            elif r.add_t in members:
                members.discard(r.add_t)
            else:
                log.append((r.date.date(), "added-not-in-set", r.add_t, r.add_n))
        if isinstance(r.rem_t, str):
            if r.rem_t in members:
                log.append((r.date.date(), "removed-already-in-set", r.rem_t, r.rem_n))
                members.add(r.rem_t + "#" + str(r.date.year))  # ticker collision -> no data
            else:
                members.add(r.rem_t)
        ci += 1
    snap[me] = sorted(members)

rows = [(me.date(), tk) for me, lst in snap.items() for tk in lst]
M = pd.DataFrame(rows, columns=["month_end", "ticker"]).sort_values(["month_end", "ticker"])
M.to_csv(DATA / "membership_monthly.csv", index=False)
L = pd.DataFrame(log, columns=["date", "issue", "ticker", "name"])
L.to_csv(DATA / "membership_issues.csv", index=False)
sz = M.groupby("month_end").size()
print(sz.iloc[::12].to_string())
print("issues:", len(L)); print(L.head(40).to_string())
ch.to_csv(DATA / "changes.csv", index=False)
print("unique tickers ever:", M.ticker.nunique())
