"""Fix release dates and add editions that s01 missed. Writes editions_fixed.jsonl.gz (s01's file is kept).

Problems found in s01's editions.jsonl.gz (2026-09-24 audit):
  * 2011-2012: the date was parsed from the text (the earliest date of that month on the page), e.g. 2011-01-03
    for the report released 2011-01-12. That is up to 12 days BEFORE the release, i.e. lookahead.
  * 2024+: the URL month is the report month, not the release month (beigebook202402 was released 2024-03-06),
    so the month-end fallback was 1-6 days BEFORE the release, i.e. lookahead.
  * 4 editions missing: 2003-09-10 (not linked on the year page), and 2011-03, 2015-03, 2023-05, which use
    8-digit URLs (beigebookYYYYMMDD.htm) that s01's regex skipped.
Release date sources, in priority order:
  1. the date in the URL (1996-2010 /fomc/beigebook/YYYY/YYYYMMDD/, and the 8-digit new-format URLs);
  2. the PDF linked next to the HTML link on the year page (fullreportYYYYMMDD.pdf / BeigeBook_YYYYMMDD.pdf);
  3. the PDF linked from the edition's own page;
  4. the page's "Last Update" stamp (only for 2017+; the 2011-2016 pages were all re-stamped 2016-12-23).
All available sources are compared, and the LATEST one wins (conservative: never trade before the release).
"""
import gzip
import html
import json
import pathlib
import re
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from s01_fetch import BASE, D, fetch, text_of  # noqa: E402

M = "January|February|March|April|May|June|July|August|September|October|November|December"
LINK = re.compile(r'href="([^"]+)"')


def canon(u: str) -> str:
    return u if u.startswith("http") else BASE + u


def year_page_pdf_dates() -> tuple[dict, list]:
    """Map edition URL -> date of the PDF linked right after it on the year page; list 8-digit URLs."""
    out, eight = {}, []
    for y in range(1996, 2026):
        page = fetch(f"{BASE}/monetarypolicy/beigebook{y}.htm")
        links = [canon(u) for u in LINK.findall(page)]
        cur = None
        for u in links:
            if re.search(r"/fomc/beigebook/\d{4}/\d{8}/default\.htm$|beigebook\d{6}(-summary)?\.htm$|beigebook\d{8}\.htm$", u):
                cur = u
                if re.search(r"beigebook\d{8}\.htm$", u):
                    eight.append(u)
            m = re.search(r"(?:fullreport|[Bb]eige[Bb]ook_)(\d{8})\.pdf", u)
            if m and cur is not None and cur not in out:
                out[cur] = pd.Timestamp(m.group(1))
    return out, sorted(set(eight))


def main():
    ed = [json.loads(l) for l in gzip.open(D / "editions.jsonl.gz", "rt")]
    ypdf, eight = year_page_pdf_dates()
    have = {e["url"] for e in ed}
    extra = [u for u in eight if u not in have]
    extra.append(f"{BASE}/fomc/beigebook/2003/20030910/default.htm")
    for u in extra:
        try:
            page = fetch(u)
        except Exception as ex:  # noqa: BLE001
            print("missing edition not fetched", u, ex); continue
        ed.append({"release": None, "url": u, "text": text_of(page)[:60000]})
        print("added", u)

    rows, log = [], []
    for e in ed:
        u = e["url"]
        raw = fetch(u)
        src = {}
        m = re.search(r"/(\d{8})/default\.htm$", u) or re.search(r"beigebook(\d{8})\.htm$", u)
        if m:
            src["url"] = pd.Timestamp(m.group(1))
        if u in ypdf:
            src["year_pdf"] = ypdf[u]
        own = sorted({pd.Timestamp(x) for x in re.findall(r"(?:fullreport|[Bb]eige[Bb]ook_)(\d{8})\.pdf", raw)})
        if len(own) == 1:
            src["own_pdf"] = own[0]
        lu = re.search(r"Last [Uu]pdate:?\s*(?:<[^>]+>\s*)*((?:" + M + r")\s+\d{1,2},\s+\d{4})", raw)
        if lu and pd.Timestamp(lu.group(1)).year >= 2017:
            src["last_update"] = pd.Timestamp(lu.group(1))
        if not src:
            raise SystemExit(f"no release date source for {u}")
        rel = max(src.values())
        spread = (max(src.values()) - min(src.values())).days
        log.append({"url": u, "old": e["release"], "release": str(rel.date()), "spread_days": spread,
                    **{k: str(v.date()) for k, v in src.items()}})
        rows.append({"release": str(rel.date()), "url": u, "text": e["text"]})
    rows.sort(key=lambda r: r["release"])
    lg = pd.DataFrame(log).sort_values("release")
    lg.to_csv(D / "release_dates_audit.csv", index=False)
    ch = lg[lg.old != lg.release]
    print(f"{len(rows)} editions; {len(ch)} release dates changed or added:")
    print(ch.to_string(index=False))
    print("editions whose sources disagree by > 0 days:")
    print(lg[lg.spread_days > 0].to_string(index=False))
    d = pd.to_datetime(lg.release)
    print("weekday counts", d.dt.day_name().value_counts().to_dict())
    print("per year", d.dt.year.value_counts().sort_index().to_dict())
    assert d.is_unique
    with gzip.open(D / "editions_fixed.jsonl.gz", "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
