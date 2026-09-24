"""Fetch each initial 13D's main document and extract Item 4 (Purpose of Transaction) plus the percent of class.

Input:  data/orch/o01_activist_13d/filings.csv (from s01)
Output: data/orch/o01_activist_13d/texts.jsonl.gz, one JSON object per accession:
        {adsh, item4, pct, n_chars, ok}
Resumable: accessions already in texts.jsonl.gz are skipped.
"""
import gzip
import html
import json
import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
from sec import get  # noqa: E402

D = ROOT / "data" / "orch" / "o01_activist_13d"
OUT = D / "texts.jsonl.gz"

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
I4 = re.compile(r"item\s*4\s*[\.\):\-–—]*\s*(?:\(?[a-z]\)?\s*)?purpose\s+of\s+(?:the\s+)?transactions?", re.I)
I5 = re.compile(r"item\s*5\s*[\.\):\-–—]*\s*(?:\(?[a-z]\)?\s*)?interests?\s+in\s+(?:the\s+)?securities", re.I)
PCT = re.compile(r"percent\s+of\s+class\s+represented\s+by\s+amount\s+in\s+row\s*\(?\s*\d+\s*\)?\s*:?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%", re.I)
XML_PURPOSE = re.compile(r"<(\w*[Pp]urpose\w*)>(.*?)</\1>", re.S)
XML_PCT = re.compile(r"<(\w*[Pp]ercent\w*)>\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*</\1>", re.S)


def clean(s: str) -> str:
    return WS.sub(" ", html.unescape(TAG.sub(" ", s))).strip()


def extract(raw: str, is_xml: bool):
    if is_xml:
        m = XML_PURPOSE.search(raw)
        item4 = clean(m.group(2)) if m else ""
        pm = XML_PCT.search(raw)
        pct = float(pm.group(2)) if pm else None
        return item4, pct
    txt = clean(raw)
    pm = PCT.search(txt)
    pct = float(pm.group(1)) if pm else None
    starts = [m.end() for m in I4.finditer(txt)]
    best = ""
    for s in starts:  # the table of contents may match first; keep the longest section
        e = I5.search(txt, s)
        seg = txt[s:e.start() if e else s + 12000]
        if len(seg) > len(best):
            best = seg
    return best[:12000].strip(" .:-"), pct


def main(limit=None):
    f = pd.read_csv(D / "filings.csv", dtype=str)
    # only filings that belong to investable, priced events (s05_events.py) -- the strategy universe
    ev = pd.read_parquet(D / "events.parquet")
    ev = ev[ev["investable"] & ev["entry_date"].notna()]
    want = {a for lst in ev["adsh_list"] for a in lst.split("|")}
    f = f[f["adsh"].isin(want)]
    done = set()
    if OUT.exists():
        with gzip.open(OUT, "rt") as fh:
            done = {json.loads(l)["adsh"] for l in fh}
    todo = f[~f["adsh"].isin(done)]
    if limit:
        todo = todo.head(int(limit))
    print("to fetch", len(todo), "done", len(done), flush=True)
    with gzip.open(OUT, "at") as fh:
        for i, r in enumerate(todo.itertuples()):
            url = f"https://www.sec.gov/Archives/edgar/data/{int(r.subject_cik)}/{r.adsh.replace('-', '')}/{r.doc}"
            try:
                raw = get(url)
                item4, pct = extract(raw, r.doc.lower().endswith(".xml"))
                rec = {"adsh": r.adsh, "item4": item4, "pct": pct, "n_chars": len(item4), "ok": True}
            except Exception as e:  # noqa: BLE001
                rec = {"adsh": r.adsh, "item4": "", "pct": None, "n_chars": 0, "ok": False, "err": str(e)[:200]}
            fh.write(json.dumps(rec) + "\n")
            if i % 200 == 0:
                fh.flush()
                print(i, r.file_date, r.ticker, rec["n_chars"], rec["pct"], flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
