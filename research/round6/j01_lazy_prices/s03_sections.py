"""Download each filing's primary document (sec.get, cache=False so raw HTML is never stored), extract sections
(Risk Factors, MD&A, Legal Proceedings) and a hashed bag-of-words of the full text, and append to
DATA/sections/<cik>.jsonl.gz. Resumable (skips accessions already stored).

usage: python s03_sections.py <from_date> <to_date> [pilot_n_ciks] [forms]
"""
import gzip
import hashlib
import threading
import queue
from collections import Counter
import json
import re
import sys
import time
from common import *
from sec import get
from extract import html_to_text, extract_sections

SD = DATA / "sections"
SD.mkdir(exist_ok=True)
NB = 4096
_W = re.compile(r"[a-z]{3,}")


def hashed_bow(text):
    out = {}
    for w, k in Counter(_W.findall(text.lower())).items():
        b = int(hashlib.md5(w.encode()).hexdigest()[:8], 16) % NB
        out[b] = out.get(b, 0) + k
    return out


def stored(cik):
    f = SD / f"{cik}.jsonl.gz"
    accs = set()
    if not f.exists():
        return accs
    try:
        with gzip.open(f, "rt") as fh:
            for ln in fh:
                try:
                    accs.add(json.loads(ln)["acc"])
                except Exception:
                    pass
    except (EOFError, OSError):
        pass
    return accs


def main():
    d0, d1 = sys.argv[1], sys.argv[2]
    pilot = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "0" else 0
    forms = sys.argv[4].split(",") if len(sys.argv) > 4 else ["10-K", "10-Q", "10-KT", "10-K405"]
    F = pd.read_csv(DATA / "filings.csv", parse_dates=["filing_date"])
    F = F[F.filing_date.between(d0, d1) & F.form.isin(forms)]
    if pilot:
        ck = pd.Series(sorted(F.cik.unique())).sample(pilot, random_state=7).tolist()
        F = F[F.cik.isin(ck)]
    print("filings to consider:", len(F), flush=True)
    t0, n, nbytes = time.time(), 0, 0
    jobs = []
    for cik, g in F.groupby("cik"):
        have = stored(cik)
        jobs += list(g[~g.acc.isin(have)].itertuples())
    print("to fetch:", len(jobs), flush=True)
    q = queue.Queue(maxsize=4)

    def producer():   # download thread (network wait only); parsing stays on the main thread
        for r in jobs:
            url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.acc.replace('-', '')}/{r.primary}"
            try:
                q.put((r, get(url, cache=False)))
            except Exception as e:
                print("fail", r.acc, e, flush=True)
        q.put(None)

    threading.Thread(target=producer, daemon=True).start()
    while True:
        item = q.get()
        if item is None:
            break
        r, h = item
        nbytes += len(h)
        txt = html_to_text(h)
        del h
        secs = extract_sections(txt, r.form)
        rec = {"acc": r.acc, "cik": int(r.cik), "form": r.form, "filing_date": str(r.filing_date.date()),
               "report_date": r.report_date, "accept": r.accept, "ticker": r.ticker,
               "n_chars": len(txt), "bow": hashed_bow(txt), **secs}
        with gzip.open(SD / f"{r.cik}.jsonl.gz", "at", compresslevel=9) as fh:
            fh.write(json.dumps(rec) + "\n")
        n += 1
        if n % 200 == 0:
            el = time.time() - t0
            print(f"{n} done, {el/n:.2f}s/filing, {nbytes/1e9:.2f} GB downloaded, "
                  f"{sum(f.stat().st_size for f in SD.glob('*.gz'))/1e6:.0f} MB stored", flush=True)
    print("finished", n, round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
