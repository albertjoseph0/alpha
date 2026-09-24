"""Point-in-time S&P 500 membership (2019-10 .. now) from Wikipedia current list + change log,
and ticker -> CIK mapping (Wikipedia CIK for current names, EDGAR entity lookup for removed ones)."""
import json, re, urllib.parse
import pandas as pd
from common import DATA, fetch

cur = pd.read_html(DATA / "sp500_wiki.html")[0]
cur["Symbol"] = cur["Symbol"].str.strip()
hist = pd.read_html(DATA / "sp500_hist.html")[0]
hist.columns = ["date", "add_t", "add_n", "rem_t", "rem_n", "reason", "refs"]
hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
hist = hist.dropna(subset=["date"])
START = pd.Timestamp("2019-10-01")
ch = hist[hist.date >= START].sort_values("date", ascending=False)

# Walk back from today's membership. intervals[ticker] = list of (start, end)
members = set(cur.Symbol)
end_of = {t: pd.Timestamp("2099-01-01") for t in members}
intervals = []
names = dict(zip(cur.Symbol, cur.Security))
for _, r in ch.iterrows():
    a, rm = r.add_t, r.rem_t
    if isinstance(a, str) and a in members:
        intervals.append((a, r.date, end_of.pop(a)))
        members.discard(a)
    if isinstance(rm, str) and rm not in members:
        members.add(rm); end_of[rm] = r.date  # member until (exclusive) change date
        names.setdefault(rm, r.rem_n)
    if isinstance(a, str):
        names.setdefault(a, r.add_n)
for t in members:
    intervals.append((t, START, end_of[t]))
iv = pd.DataFrame(intervals, columns=["ticker", "start", "end"])
iv["name"] = iv.ticker.map(names)
print("membership intervals:", len(iv), "unique tickers:", iv.ticker.nunique())

# CIK mapping
cik = {r.Symbol: int(r.CIK) for r in cur.itertuples()}
ct = json.loads(open(DATA / "company_tickers.json").read())
sec_t = {v["ticker"].upper(): int(v["cik_str"]) for v in ct.values()}
rows = []
for t in sorted(iv.ticker.unique()):
    src = "wiki"
    c = cik.get(t)
    if c is None:
        nm = names.get(t, t)
        q = re.sub(r"\(.*?\)|,? Inc\.?|Corporation|Corp\.?|Company|plc|Ltd\.?|Holdings?|Group|The ", " ", str(nm)).strip()
        js = fetch("https://efts.sec.gov/LATEST/search-index?keysTyped=" + urllib.parse.quote(q))
        hits = json.loads(js)["hits"]["hits"] if js else []
        # prefer a hit whose ticker list contains the old ticker, else top-ranked hit
        best = None
        for h in hits:
            tk = h["_source"].get("tickers", "") or ""
            if t in [x.strip() for x in tk.split(",")]:
                best = h; src = "efts_ticker"; break
        if best is None and hits:
            best = max(hits[:5], key=lambda h: h["_source"].get("rank", 0)); src = "efts_name"
        c = int(best["_id"]) if best else None
        ent = best["_source"]["entity"] if best else None
    else:
        ent = None
    rows.append((t, names.get(t), c, src, ent))
m = pd.DataFrame(rows, columns=["ticker", "name", "cik", "src", "efts_entity"])
iv = iv.merge(m[["ticker", "cik"]], on="ticker", how="left")
iv.to_csv(DATA / "sp500_pit_intervals.csv", index=False)
m.to_csv(DATA / "ticker_cik.csv", index=False)
print(m.src.value_counts())
print(m[m.src != "wiki"].to_string())

# manual fixes for wrong EDGAR entity-name matches (checked by hand)
FIX = {"AIV": 922864, "ETFC": 1015780, "NLSN": 1492633, "CDAY": 1725057, "ARNC": 4281}
m = pd.read_csv(DATA / "ticker_cik.csv")
for t, c in FIX.items():
    m.loc[m.ticker == t, ["cik", "src"]] = [c, "manual"]
m.to_csv(DATA / "ticker_cik.csv", index=False)
iv = iv.drop(columns="cik").merge(m[["ticker", "cik"]], on="ticker", how="left")
iv.to_csv(DATA / "sp500_pit_intervals.csv", index=False)
print("fixed", FIX)
