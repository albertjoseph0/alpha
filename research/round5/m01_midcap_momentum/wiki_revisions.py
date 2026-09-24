"""Independent point-in-time S&P 400 membership from Wikipedia's own revision history.

For every month-end 2011-12 .. 2026-08 take the last revision of "List of S&P 400 companies" saved
on or before that date (strictly point-in-time: a revision only contains what editors knew then),
download its wikitext (cached, gzip) and parse the constituent tickers.
Output (NEW files, the shared membership_monthly.csv is untouched):
  DATA/wiki_rev/<revid>.txt.gz, DATA/wiki_rev/revisions.csv, DATA/membership_wikirev.csv
"""
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from common import *

UA = {"User-Agent": "alpha-research contact@alpha-research.dev"}
API = "https://en.wikipedia.org/w/api.php?"
RD = DATA / "wiki_rev"
RD.mkdir(exist_ok=True)
TITLE = "List of S&P 400 companies"


def get(params):
    url = API + urllib.parse.urlencode(params)
    for k in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            print("retry", e, flush=True)
            time.sleep(20 * (k + 1))
    raise RuntimeError(url)


def revision_list():
    f = RD / "revisions.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["ts"])
    rows, cont = [], {}
    while True:
        j = get(dict(action="query", prop="revisions", titles=TITLE, rvlimit=500, rvdir="newer",
                     rvprop="ids|timestamp|size", format="json", **cont))
        for p in j["query"]["pages"].values():
            rows += [(r["revid"], r["timestamp"], r["size"]) for r in p["revisions"]]
        if "continue" not in j:
            break
        cont = {"rvcontinue": j["continue"]["rvcontinue"], "continue": j["continue"]["continue"]}
        time.sleep(1)
    R = pd.DataFrame(rows, columns=["revid", "ts", "size"])
    R["ts"] = pd.to_datetime(R["ts"]).dt.tz_localize(None)
    R.to_csv(f, index=False)
    return R


def wikitext(revid):
    f = RD / f"{revid}.txt.gz"
    if f.exists():
        return gzip.open(f, "rt").read()
    url = ("https://en.wikipedia.org/w/index.php?title=" + urllib.parse.quote(TITLE.replace(" ", "_"))
           + f"&oldid={revid}&action=raw")      # raw endpoint: not subject to the API's 429 limits
    txt = None
    for k in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                txt = r.read().decode("utf-8")
            break
        except Exception as e:
            print("retry raw", e, flush=True)
            time.sleep(20 * (k + 1))
    gzip.open(f, "wt").write(txt)
    time.sleep(1.5)
    return txt


SYM = re.compile(r"\{\{\s*(?:NyseSymbol|NYSE|NasdaqSymbol|NASDAQ|Nasdaq|nyse|nasdaq|NYSE[ _]?link|"
                 r"Nasdaq[ _]?link|NYSEArca|AMEX|BATS)\s*\|\s*([A-Za-z0-9.\-/]+)", re.I)
LINK = re.compile(r"^\|\s*\[https?://[^\s\]]+\s+([A-Z0-9.\-/]+)\]")
PLAIN = re.compile(r"^\|\s*([A-Z][A-Z0-9.\-/]{0,6})\s*(?:\|\||$)")


def parse(txt):
    """Tickers of the FIRST wikitable (the constituents list; the changes table comes later)."""
    i = txt.find("{|")
    if i < 0:
        return set()
    j = txt.find("\n|}", i)
    body = txt[i:j if j > 0 else None]
    rows = re.split(r"\n\|-", body)
    out = set()
    for r in rows[1:]:
        lines = [l for l in r.strip().split("\n") if l.startswith("|") and not l.startswith("|+")]
        if not lines:
            continue
        first = lines[0]
        m = SYM.search("\n".join(lines)) or LINK.search(first) or PLAIN.search(first)
        if m:
            out.add(m.group(1).strip().replace(".", "-").upper())
    return out


if __name__ == "__main__":
    R = revision_list().sort_values("ts")
    print("revisions:", len(R), R.ts.min(), R.ts.max())
    months = pd.date_range("2011-12-31", "2026-08-31", freq="ME")
    rows, meta = [], []
    for me in months:
        cut = me + pd.Timedelta(hours=23, minutes=59)
        sub = R[R.ts <= cut]
        rid = int(sub.revid.iloc[-1])
        tk = parse(wikitext(rid))
        meta.append((me.date(), rid, sub.ts.iloc[-1], len(tk)))
        rows += [(me.date(), t) for t in sorted(tk)]
        if me.month == 12:
            print(me.date(), rid, len(tk), flush=True)
    W = pd.DataFrame(rows, columns=["month_end", "ticker"])
    W.to_csv(DATA / "membership_wikirev.csv", index=False)
    pd.DataFrame(meta, columns=["month_end", "revid", "rev_ts", "n"]).to_csv(DATA / "membership_wikirev_meta.csv",
                                                                           index=False)
    print(W.groupby("month_end").size().describe())
