"""Text helpers: HTML/SEC submission -> plain text, snippet extraction, price/date parsing."""
import html
import re

import pandas as pd

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}})\s*,?\s+(\d{{4}})")
MONEY_RE = re.compile(r"\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)(?!\d)")


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("•", "-")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def split_submission(s: str):
    """Full .txt submission -> list of (type, filename, text)."""
    out = []
    for m in re.finditer(r"(?s)<DOCUMENT>(.*?)</DOCUMENT>", s):
        d = m.group(1)
        ty = re.search(r"<TYPE>([^\n<]+)", d)
        fn = re.search(r"<FILENAME>([^\n<]+)", d)
        body = re.search(r"(?s)<TEXT>(.*)</TEXT>", d)
        body = body.group(1) if body else d
        if re.search(r"(?i)<html|<p[ >]|<div|<table", body[:5000]):
            body = html_to_text(body)
        else:
            body = re.sub(r"[ \t]+", " ", html.unescape(body))
        out.append(((ty.group(1).strip() if ty else ""), (fn.group(1).strip() if fn else ""), body))
    return out


def one_line(t: str) -> str:
    return re.sub(r"\s+", " ", t)


def parse_date(m) -> pd.Timestamp:
    try:
        return pd.Timestamp(f"{m.group(1)} {int(m.group(2))} {m.group(3)}")
    except Exception:
        return pd.NaT


def price_snippets(t: str, width: int = 450):
    """Windows starting at a date and containing a closing-price statement and a $ amount."""
    t = one_line(t)
    out = []
    for m in DATE_RE.finditer(t):
        w = t[m.start(): m.start() + width]
        if re.search(r"(?i)clos|sale price|sales price|last reported|trading price", w) and "$" in w:
            out.append(w)
    return out


def keyword_snippets(t: str, pats, width: int = 300, maxn: int = 40):
    t = one_line(t)
    out = []
    for p in pats:
        for m in re.finditer(p, t):
            out.append(t[max(0, m.start() - width): m.end() + width])
            if len(out) >= maxn:
                return out
    return out


def parse_price_statement(w: str):
    """Snippet starting with a date -> (date, first $ amount after a closing-price cue, cue text)."""
    m = DATE_RE.match(w)
    if not m:
        return None
    d = parse_date(m)
    rest = w[m.end():]
    cue = re.search(r"(?i)clos\w*|sales? price|last reported|trading price", rest)
    if not cue:
        return None
    mm = MONEY_RE.search(rest, cue.start())
    if not mm or mm.start() - cue.start() > 250:
        return None
    # the statement must not jump to another date before the $ amount
    mid = rest[: mm.start()]
    if DATE_RE.search(mid):
        return None
    try:
        px = float(mm.group(1).replace(",", ""))
    except ValueError:
        return None
    return d, px, rest[: mm.end() + 40]


CASH_RE = [
    re.compile(r"\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)\s*(?:per\s+(?:share|Share|Company Share|share of[^,$]{0,60}?)\s*,?\s*)?(?:net to the (?:seller|holder)s?\s*(?:thereof\s*)?)?,?\s*in cash", re.I),
    re.compile(r"(?:amount|right to receive)\s+in cash\s+(?:equal to\s+)?\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)", re.I),
    re.compile(r"cash (?:consideration |payment )?(?:of|equal to)\s+\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)\s*per\s+share", re.I),
]


def cash_prices(t: str):
    t = one_line(t)
    vals = []
    for r in CASH_RE:
        for m in r.finditer(t):
            try:
                v = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if 0.05 <= v <= 5000:
                vals.append(v)
    return vals
