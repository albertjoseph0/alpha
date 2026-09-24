"""Narrative extraction and anonymisation of earnings press releases (for Jev states).
Removes company names, tickers, URLs and dates (years, month-day, fiscal-year labels); keeps numbers
such as percentages and dollar amounts, which carry the facts."""
import re

NARR_MIN_WORDS = 8
KEYW = re.compile(r"outlook|guidance|expect|forecast|full[- ]year|fiscal|range", re.I)
MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
RE_MDY = re.compile(MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s*(?:19|20)\d{2}", re.I)
RE_MD = re.compile(r"\b" + MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?\b", re.I)
RE_MY = re.compile(r"\b" + MONTHS + r"\s+(?:19|20)\d{2}\b", re.I)
RE_NUMDATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
RE_YEAR = re.compile(r"(?<![\d$.,])(?:19|20)\d{2}(?![\d%])")
RE_FY = re.compile(r"\b(FY|Q[1-4]\s*(?:FY)?|F)'?\s?\d{2}\b", re.I)
RE_WEEKDAY = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b,?", re.I)
RE_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
RE_EXCH = re.compile(r"\((?:NYSE|NASDAQ|Nasdaq|NYSE American|Cboe)\s*(?::|-)\s*[A-Z.]{1,6}\)")
SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|plc|ltd|limited|holdings?|group|n\.?v|s\.?a|lp|l\.p|the|class [a-c]|/de/|/new/|/md/|de)\b\.?", re.I)
COMMON = {"american", "general", "united", "first", "international", "national", "global", "new", "public",
          "southern", "western", "eastern", "northern", "digital", "applied", "advanced", "consolidated",
          "universal", "federal", "republic", "royal", "life", "energy", "health", "capital", "financial",
          "data", "state", "best", "home", "old", "power", "service", "services", "live", "ball", "target",
          "gap", "match", "news", "fox", "dollar", "discovery", "progressive", "principal", "equity",
          "realty", "trust", "bank", "air", "west", "east", "north", "south", "texas", "pacific", "atlantic"}


def name_patterns(company, name, ticker):
    """Regexes for the firm's identifiers: full names, names without suffixes, distinctive first word,
    ticker (word-bounded, case-sensitive)."""
    pats = set()
    for n in (company, name):
        if not isinstance(n, str) or not n.strip():
            continue
        n = re.sub(r"\s+", " ", n).strip()
        pats.add(n)
        core = re.sub(r"\s+", " ", SUFFIX.sub(" ", n)).strip(" ,.&")
        if len(core) >= 3:
            pats.add(core)
        w = core.split()
        if w and len(w[0]) >= 4 and w[0].lower() not in COMMON:
            pats.add(w[0])
        if len(w) >= 2:
            pats.add(" ".join(w[:2]))
    out = [re.compile(r"\b" + re.escape(p) + r"(?:'s|’s)?\b", re.I) for p in sorted(pats, key=len, reverse=True)]
    if isinstance(ticker, str) and ticker:
        for t in {ticker, ticker.replace("-", "."), ticker.split("-")[0].split(".")[0]}:
            if len(t) >= 2:
                out.append(re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?:'s|’s)?(?![A-Za-z])"))
    return out


def anonymise(text, pats):
    text = RE_URL.sub("[URL]", text)
    text = RE_EXCH.sub("", text)
    for p in pats:
        text = p.sub("the Company", text)
    text = RE_MDY.sub("[DATE]", text)
    text = RE_NUMDATE.sub("[DATE]", text)
    text = RE_MY.sub("[DATE]", text)
    text = RE_MD.sub("[DATE]", text)
    text = RE_FY.sub(lambda m: re.sub(r"\d{2}$", "[YR]", m.group(0)), text)
    text = RE_YEAR.sub("[YEAR]", text)
    text = RE_WEEKDAY.sub("", text)
    return text


def narrative(text, max_chars=12000):
    """Narrative lines (>= 8 words, mostly letters) plus short outlook lines, in document order."""
    out, n = [], 0
    for line in (c for l in text.split("\n") for c in l.split("|")):
        line = line.strip(" •●▪·–-*\t")
        if not line:
            continue
        words = line.split()
        letters = sum(ch.isalpha() for ch in line)
        ok = len(words) >= NARR_MIN_WORDS and letters / max(len(line), 1) >= 0.5
        ok = ok or (len(words) >= 3 and KEYW.search(line) and letters / max(len(line), 1) >= 0.3)
        if ok:
            out.append(line)
            n += len(line) + 1
            if n >= max_chars:
                break
    return "\n".join(out)[:max_chars]
