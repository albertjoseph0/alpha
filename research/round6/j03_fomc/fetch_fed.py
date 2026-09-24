"""Fetch FOMC meetings (1994 -> latest), statements and minutes from federalreserve.gov.

Outputs (data/round6/j03_fomc/):
  meetings.csv   one row per FOMC meeting/call: header, decision date, statement url, minutes url, minutes release date
  docs/<kind>_<YYYYMMDD>.txt   cleaned plain text of each statement / minutes page
Polite: fixed User-Agent, 1 request/second, disk cache of raw HTML in raw/.
"""
import html
import re
import sys
import time
import pathlib
import urllib.request
from datetime import date

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "round6" / "j03_fomc"
RAW = D / "raw"
DOCS = D / "docs"
RAW.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
UA = "alpha-research contact@alpha-research.dev"
BASE = "https://www.federalreserve.gov"
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MABBR = {k[:3]: v for k, v in MONTHS.items()}


def fetch(url: str, name: str) -> str:
    p = RAW / name
    if p.exists() and p.stat().st_size > 2000:
        return p.read_text(errors="ignore")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            break
        except Exception as e:  # noqa
            print("  retry", url, e, file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    else:
        return ""
    time.sleep(1.0)
    t = b.decode("utf-8", errors="ignore")
    p.write_text(t)
    return t


def html_to_text(t: str) -> str:
    t = re.sub(r"(?is)<(script|style|head|nav|footer).*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>|</tr>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()


def parse_date_text(s: str):
    """'Released Feb 20, 2008' / 'Released February 18, 2026' -> date"""
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4})", s)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower()) or MABBR.get(m.group(1).lower()[:3])
    return date(int(m.group(3)), mon, int(m.group(2))) if mon else None


def header_last_day(h: str, year: int):
    """'January 30-31 Meeting - 1996', 'April/May 30-1 Meeting', 'June 30-July 1 Meeting', 'October 4 (unscheduled)'."""
    h = h.replace("\xa0", " ")
    months = re.findall(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*", h)
    days = re.findall(r"(\d{1,2})(?!\d)", h.split(" - ")[0])
    if not months or not days:
        return None
    return date(year, MABBR[months[-1].lower()], int(days[-1]))


def yyyymmdd(url: str):
    m = re.search(r"((?:19|20)\d{6})", url)
    return m.group(1) if m else None


def parse_historical(year: int):
    t = fetch(f"{BASE}/monetarypolicy/fomchistorical{year}.htm", f"h{year}.htm")
    rows = []
    for panel in re.split(r'<div class="panel panel-default', t)[1:]:
        hm = re.search(r"<h5[^>]*>(.*?)</h5>", panel, re.S)
        if not hm:
            continue
        head = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", hm.group(1))).strip()
        links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', panel, re.S)
        stmt = [h for h, x in links if re.sub("<[^>]+>", "", x).strip().lower() == "statement"]
        mins = [h for h, x in links if re.search(r"minutes", h, re.I) and h.lower().endswith((".htm", ".html"))
                and "#" not in h and not re.search(r"(?i)memo", h)]
        rel = re.search(r"Released\s+([^)<]*)", panel)
        rows.append(dict(year=year, header=head, kind=("call" if re.search(r"call|unscheduled", head, re.I) else "meeting"),
                         last_day=header_last_day(head, year), statement_url=stmt[0] if stmt else None,
                         minutes_url=mins[0] if mins else None,
                         minutes_release=parse_date_text(rel.group(0)) if rel else None))
    return rows


def parse_calendar():
    t = fetch(f"{BASE}/monetarypolicy/fomccalendars.htm", "cal.htm")
    rows = []
    for yb in re.split(r'<h4><a id="\d+">', t)[1:]:
        year = int(yb[:4])
        for mb in re.split(r'class="[^"]*row fomc-meeting"', yb)[1:]:
            mon = re.search(r"fomc-meeting__month[^>]*><strong>([^<]*)</strong>", mb)
            day = re.search(r"fomc-meeting__date[^>]*>([^<]*)</div>", mb)
            if not mon or not day:
                continue
            head = f"{mon.group(1)} {day.group(1).strip()} - {year}"
            links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', mb, re.S)
            stmt = [h for h, x in links if re.search(r"/monetary\d{8}a\.htm$", h)]
            mins = [h for h, x in links if re.search(r"fomcminutes\d{8}\.htm$", h)]
            rel = re.search(r"Released\s+([^)<]*)", mb)
            unsched = "unscheduled" in mb.lower() or "notation" in mb.lower()
            rows.append(dict(year=year, header=head, kind=("call" if unsched else "meeting"),
                             last_day=header_last_day(head, year), statement_url=stmt[0] if stmt else None,
                             minutes_url=mins[0] if mins else None,
                             minutes_release=parse_date_text(rel.group(0)) if rel else None))
    return rows


def main():
    rows = []
    for y in range(1994, 2021):
        rows += parse_historical(y)
    rows += parse_calendar()
    m = pd.DataFrame(rows)
    m = m[(m.year >= 1994) & (m.statement_url.notna() | m.minutes_url.notna())].copy()
    # decision date: statement url date if present (statement released that day), else last meeting day
    m["stmt_date"] = [pd.to_datetime(yyyymmdd(u)) if isinstance(u, str) and yyyymmdd(u) else pd.NaT for u in m.statement_url]
    m["decision_date"] = m.stmt_date.fillna(pd.to_datetime(m.last_day))
    # HTML minutes missing but PDF present (e.g. 2008-06): build the standard url
    fix = m.minutes_url.isna() & m.minutes_release.notna() & (m.kind == "meeting") & m.stmt_date.notna() & (m.year >= 2007)
    m.loc[fix, "minutes_url"] = ["/monetarypolicy/fomcminutes%s.htm" % d.strftime("%Y%m%d") for d in m.loc[fix, "stmt_date"]]
    m = m.sort_values("decision_date").drop_duplicates(["decision_date", "header"]).reset_index(drop=True)
    m.to_csv(D / "meetings_raw.csv", index=False)
    print(m.groupby("year").agg(n=("header", "size"), stmts=("statement_url", "count"), mins=("minutes_url", "count"),
                                rel=("minutes_release", "count")).to_string())
    # download docs
    for _, r in m.iterrows():
        for kind, url in (("stmt", r.statement_url), ("min", r.minutes_url)):
            if not isinstance(url, str):
                continue
            ds = r.decision_date.strftime("%Y%m%d") if kind == "stmt" else (yyyymmdd(url) or r.decision_date.strftime("%Y%m%d"))
            out = DOCS / f"{kind}_{ds}.txt"
            if out.exists():
                continue
            full = url if url.startswith("http") else BASE + url
            t = fetch(full, f"{kind}_{ds}.htm")
            if t:
                out.write_text(html_to_text(t))
                print("got", out.name, len(t))
    m.to_csv(D / "meetings.csv", index=False)


if __name__ == "__main__":
    main()
