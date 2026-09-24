"""Step 3: map each exchange-listed spin-off to its first regular-way trading date and prices.
* EDGAR submissions JSON (via sec.get) per CIK: completed (periodic reports after the Form 10), current tickers,
  fate flags (merger filings, 15-12/25 deregistration, bankruptcy 8-K item 1.03).
* yfinance daily history (auto_adjust=False, with splits) for the doc ticker, else the EDGAR current ticker.
  A series is accepted only if it starts between first Form 10 filing - 5 days and last doc date + 180 days.
* Parent ticker: doc regex, else current SEC company_tickers.json name match; parent price is used only for
  the size-mismatch ratio f = r*P_spin / (r*P_spin + P_parent) on the first regular-way day (unadjusted prices).
Outputs data/round6/j04_spinoffs/events.csv and prices/<ticker>.csv."""
import json, os, re, sys, time
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = "/home/user/alpha"
sys.path.insert(0, f"{ROOT}/research/round5")
from sec import get  # noqa: E402

D = f"{ROOT}/data/round6/j04_spinoffs"
P = f"{D}/prices"
os.makedirs(P, exist_ok=True)
meta = pd.read_csv(f"{D}/meta.csv")
ev = meta[meta.is_spin_doc & (meta.spin_exch.isin(["NYSE", "NASDAQ", "AMEX"]) | meta.spin_exch.isna())].copy()
print(len(ev), "exchange-listed spin docs")


def hist(tk):
    f = f"{P}/{tk}.csv"
    if os.path.exists(f):
        h = pd.read_csv(f, index_col=0, parse_dates=True)
        return h if len(h) else None
    try:
        h = yf.Ticker(tk).history(period="max", auto_adjust=False, actions=True)
    except Exception as e:  # noqa: BLE001
        print("yf err", tk, e)
        h = pd.DataFrame()
    time.sleep(0.4)
    if h is None or len(h) == 0:
        pd.DataFrame().to_csv(f)
        return None
    h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
    h = h[["Open", "High", "Low", "Close", "Adj Close", "Volume", "Stock Splits"]]
    h.to_csv(f)
    return h


def subs(cik):
    try:
        return json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
    except Exception as e:  # noqa: BLE001
        print("subs err", cik, e)
        return None


ct = json.loads(get("https://www.sec.gov/files/company_tickers.json"))
ct = pd.DataFrame(ct.values())
ct["t0"] = ct.title.str.upper().str.replace(r"[^A-Z0-9 ]", "", regex=True).str.split().str[0]

rows = []
for _, r in ev.iterrows():
    s = subs(r.cik)
    info = dict(cik=r.cik)
    lo = pd.Timestamp(r.first_form10) - pd.Timedelta(days=5)
    hi = pd.Timestamp(r.doc_date) + pd.Timedelta(days=180)
    fl = None
    if s:
        rec = pd.DataFrame(s["filings"]["recent"])
        rec["filingDate"] = pd.to_datetime(rec.filingDate)
        after = rec[rec.filingDate > pd.Timestamp(r.doc_date)]
        info["completed"] = bool(after.form.isin(["10-K", "10-Q", "10-K405", "20-F", "40-F"]).any())
        info["merger_filings"] = bool(rec.form.isin(["DEFM14A", "SC 14D9", "PREM14A", "DEFM14C", "SC TO-T", "S-4 POS"]).any())
        info["dereg"] = bool(rec.form.isin(["15-12B", "15-12G", "25-NSE", "15-15D"]).any())
        info["bankrupt"] = bool(rec["items"].astype(str).str.contains(r"1\.03").any()) if "items" in rec else False
        info["last_filing"] = rec.filingDate.max().date() if len(rec) else None
        info["edgar_tickers"] = ",".join(s.get("tickers") or [])
        info["sic"] = float(s["sic"]) if s.get("sic") else None
        info["edgar_exchanges"] = ",".join(str(x) for x in (s.get("exchanges") or []) if x)
        info["n_recent"] = len(rec)
        if len(s["filings"].get("files", [])):
            info["older_pages"] = len(s["filings"]["files"])
    cands = ([str(r.spin_ticker).replace(".", "-")] if isinstance(r.spin_ticker, str) else []) + [t.replace(".", "-") for t in (info.get("edgar_tickers") or "").split(",") if t]
    used = None
    for tk in dict.fromkeys(cands):
        h = hist(tk)
        if h is None:
            continue
        h = h[h.Close > 0]
        if len(h) and lo <= h.index[0] <= hi:
            used, fl = tk, h
            break
        info.setdefault("rejected", []).append(f"{tk}:{h.index[0].date() if len(h) else 'empty'}")
    info["yf_ticker"] = used
    if used:
        info["first_trade"] = fl.index[0].date()
        info["last_trade"] = fl.index[-1].date()
        info["p0_close"] = fl.Close.iloc[0]
        # undo later splits to get the as-traded day-0 price
        spl = fl["Stock Splits"].replace(0, 1.0)
        fac = spl[spl.index > fl.index[0]].prod()
        info["p0_unadj"] = fl.Close.iloc[0] * fac
        info["adv20_usd"] = float((fl.Close * fl.Volume).iloc[:20].median() * 1.0)
    # parent ticker
    pt = r.parent_ticker if isinstance(r.parent_ticker, str) else None
    if pt is None and isinstance(r.parent_name, str):
        m = ct[ct.t0 == re.sub(r"[^A-Z0-9]", "", r.parent_name.upper())]
        if len(m) == 1:
            pt = m.ticker.iloc[0]
            info["parent_from"] = "sec_name"
    info["parent_yf"] = pt
    if pt:
        m = ct[ct.ticker == pt.replace(".", "-")]
        if len(m):
            ps = subs(m.cik_str.iloc[0])
            info["parent_sic"] = float(ps.get("sic")) if ps and ps.get("sic") else None
    if used and pt:
        hp = hist(pt.replace(".", "-"))
        if hp is not None and len(hp):
            d0 = fl.index[0]
            hp = hp[hp.Close > 0]
            if hp.index[0] < d0 - pd.Timedelta(days=30) and d0 in hp.index:
                spl = hp["Stock Splits"].replace(0, 1.0)
                info["pp0_unadj"] = hp.Close.loc[d0] * spl[spl.index > d0].prod()
    info.pop("rejected", None) if not info.get("rejected") else info.update(rejected=";".join(info["rejected"]))
    rows.append(info)
    if len(rows) % 25 == 0:
        print(len(rows), flush=True)

x = pd.DataFrame(rows)
out = ev.merge(x, on="cik", how="left")
out["f_size"] = np.where(out.ratio.notna() & out.pp0_unadj.notna(),
                         out.ratio * out.p0_unadj / (out.ratio * out.p0_unadj + out.pp0_unadj), np.nan)
out["mcap0"] = out.shares_doc * out.p0_unadj
out.to_csv(f"{D}/events.csv", index=False)
print(out.yf_ticker.notna().mean(), "with prices;", out.completed.mean(), "completed")
