"""(Round 5b copy of 04_fetch_prices.py reading events_v2.parquet.)
Fetch daily prices from yfinance for every candidate ticker of every event.
Candidates: (a) the ticker on the Form 4 filing, (b) the issuer's CURRENT ticker(s) from SEC
company_tickers.json via CIK (recovers renamed / re-tickered issuers).
Stores long-format parquet trimmed to [first event - 400d, last event + 420d] per ticker."""
import json, os, time, sys, re
import numpy as np, pandas as pd, yfinance as yf

D = "/home/user/alpha/data/round5/m05_insider_clusters"
ev = pd.read_parquet(f"{D}/events_v2.parquet")
ct = json.load(open(f"{D}/company_tickers.json"))
cik2t = {}
for v in ct.values():
    cik2t.setdefault(str(v["cik_str"]), []).append(v["ticker"])

def clean(s):
    s = (s or "").upper().strip()
    s = re.split(r"[\s,;/]+", s)[0] if s else ""
    s = s.replace(".", "-")
    if not re.fullmatch(r"[A-Z][A-Z0-9\-]{0,6}", s) or s in ("NONE", "NA", "N-A"):
        return ""
    return s

cand = []
for r in ev.itertuples():
    c = [clean(r.sym)] + [clean(t) for t in cik2t.get(str(r.cik), [])]
    c = [x for x in dict.fromkeys(c) if x]
    for x in c:
        cand.append((r.Index, x))
cand = pd.DataFrame(cand, columns=["ev", "ticker"])
cand.to_parquet(f"{D}/event_candidates_v2.parquet", index=False)
win = cand.merge(ev[["fdate"]], left_on="ev", right_index=True).groupby("ticker").fdate.agg(["min", "max"])
print("events", len(ev), "with any candidate", cand.ev.nunique(), "unique tickers", len(win), flush=True)

out_dir = f"{D}/px"; os.makedirs(out_dir, exist_ok=True); os.makedirs(f"{D}/splits", exist_ok=True)
done = {f[:-8] for f in os.listdir(out_dir)}
todo = [t for t in win.index if t not in done]
missing_f = f"{D}/px_missing.txt"
missing = set(open(missing_f).read().split()) if os.path.exists(missing_f) else set()
todo = [t for t in todo if t not in missing]
print("todo", len(todo), flush=True)
B = int(os.environ.get("YF_BATCH", 40))
for i in range(0, len(todo), B):
    batch = todo[i:i + B]
    try:
        d = yf.download(batch, start="2005-01-01", auto_adjust=False, actions=True, progress=False,
                        group_by="ticker", threads=os.environ.get("YF_THREADS", "1") == "1", timeout=30)
    except Exception as e:
        print("ERR", e, flush=True); time.sleep(10); continue
    for t in batch:
        try:
            x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            x = x.dropna(subset=["Close"])
        except Exception:
            x = pd.DataFrame()
        if len(x) == 0:
            missing.add(t); continue
        sp = x["Stock Splits"]; sp = sp[(sp > 0) & (sp != 1)]
        if len(sp):
            sp.rename("ratio").to_frame().to_parquet(f"{D}/splits/{t}.parquet")
        lo = win.loc[t, "min"] - pd.Timedelta(days=400); hi = win.loc[t, "max"] + pd.Timedelta(days=420)
        x = x[(x.index >= lo) & (x.index <= hi)]
        if len(x) == 0:
            missing.add(t); continue
        x = x[["Close", "Adj Close", "Volume", "Stock Splits", "High", "Low"]].astype("float32")
        x.columns = ["close", "adj", "vol", "split", "high", "low"]
        x.to_parquet(f"{out_dir}/{t}.parquet")
    open(missing_f, "w").write("\n".join(sorted(missing)))
    print(i + len(batch), "/", len(todo), "missing so far", len(missing), flush=True)
    time.sleep(2)
