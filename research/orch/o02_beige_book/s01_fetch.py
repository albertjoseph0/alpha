"""Fetch every Beige Book national summary 1996-2026 from federalreserve.gov.

Formats:
  1996-2010: /fomc/beigebook/YYYY/YYYYMMDD/default.htm      (the national summary; date in the URL)
  2011-2023: /monetarypolicy/beigebookYYYYMM.htm           (full report; the national summary comes first)
  2024+    : /monetarypolicy/beigebookYYYYMM-summary.htm   (national summary)
The release date for the newer formats is parsed from the page text. Beige Books are released at 14:00 ET
on the release date, so the first tradeable close is that day's close; we use the NEXT close (1-day lag).
Output: data/orch/o02_beige_book/editions.jsonl.gz  {release, url, text}
"""
import gzip
import html
import json
import pathlib
import re
import time
import urllib.request

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "orch" / "o02_beige_book"
D.mkdir(parents=True, exist_ok=True)
UA = "alpha-research contact@alpha-research.dev"
BASE = "https://www.federalreserve.gov"
TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
WS = re.compile(r"\s+")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"({MONTHS})\s+(\d{{1,2}}),\s+((?:19|20)\d{{2}})")


def fetch(url: str) -> str:
    cache = D / "cache" / (re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:] + ".html")
    if cache.exists():
        return cache.read_text()
    time.sleep(0.5)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        s = r.read().decode("utf-8", errors="replace")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(s)
    return s


def text_of(page: str) -> str:
    t = WS.sub(" ", html.unescape(TAG.sub(" ", page)))
    i = t.find("Overall Economic Activity")
    if i < 0:
        i = t.find("National Summary")
    return t[max(i, 0):]


def main():
    links, pdf_dates = [], {}
    pages = [(y, f"{BASE}/monetarypolicy/beigebook{y}.htm") for y in range(1996, 2026)]
    pages.append((2026, f"{BASE}/monetarypolicy/publications/beige-book-default.htm"))
    for y, purl in pages:
        try:
            page = fetch(purl)
        except Exception as e:  # noqa: BLE001
            print("year", y, e); continue
        for dt in re.findall(r"[Bb]eige[Bb]ook_(\d{8})\.pdf", page):
            pdf_dates[dt[:6]] = pd.Timestamp(dt)
        old = sorted(set(re.findall(r'href="((?:https://www\.federalreserve\.gov)?/fomc/beigebook/\d{4}/\d{8}/default\.htm)"', page)))
        new_s = sorted(set(re.findall(r'href="(/monetarypolicy/beigebook\d{6}-summary\.htm)"', page)))
        new_f = sorted(set(re.findall(r'href="((?:https://www\.federalreserve\.gov)?/monetarypolicy/(?:beigebook/)?beigebook\d{6}\.htm)"', page)))
        months_f = {re.search(r"(\d{6})", u).group(1) for u in new_f}
        # prefer the full report (sector detail lives in the district sections); summary only if no full page
        new = new_f + [u for u in new_s if re.search(r"(\d{6})", u).group(1) not in months_f]
        links += [u if u.startswith("http") else BASE + u for u in old + new]
        print(y, len(old), len(new), flush=True)
    rows = []
    for u in links:
        try:
            page = fetch(u)
        except Exception as e:  # noqa: BLE001
            print("skip", u, e); continue
        m = re.search(r"/(\d{8})/default\.htm", u)
        if m:
            release = pd.Timestamp(m.group(1))
        else:
            raw = WS.sub(" ", html.unescape(TAG.sub(" ", page)))
            ym = re.search(r"beigebook(\d{4})(\d{2})", u)
            cands = [pd.Timestamp(f"{mo} {d}, {yr}") for mo, d, yr in DATE.findall(raw[:6000])]
            cands = [c for c in cands if c.year == int(ym.group(1)) and c.month == int(ym.group(2))]
            key = ym.group(1) + ym.group(2)
            if key in pdf_dates:
                release = pdf_dates[key]
            elif cands:
                release = min(cands)
            else:  # unknown day: use month end (conservative: never trade before the true release)
                release = pd.Timestamp(f"{ym.group(1)}-{ym.group(2)}-01") + pd.offsets.MonthEnd(0)
        rows.append({"release": str(release.date()), "url": u, "text": text_of(page)[:60000]})
    rows.sort(key=lambda r: r["release"])
    with gzip.open(D / "editions.jsonl.gz", "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print("editions", len(rows), rows[0]["release"], rows[-1]["release"])


if __name__ == "__main__":
    main()
