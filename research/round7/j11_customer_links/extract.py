"""10-K HTML -> plain text -> candidate major-customer sentences and candidate customer names (regex only).

A candidate sentence contains a percentage (or 'ten percent') and a customer/revenue keyword.  Candidate names are
runs of capitalised words inside such sentences, minus a stop list.  Everything here is deterministic code."""
import html as _html
import re

_DROP = re.compile(r"(?is)<(script|style|ix:header|head)\b[^>]*>.*?</\1\s*>")
_TAG = re.compile(r"(?s)<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v  ​]+")


def html_to_text(h: str) -> str:
    h = _DROP.sub(" ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p\s*>|</div\s*>|</tr\s*>|</li\s*>|</h\d\s*>", "\n", h)
    h = re.sub(r"(?i)</t[dh]\s*>", " | ", h)
    h = _TAG.sub(" ", h)
    h = _html.unescape(h)
    h = h.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    h = h.replace("–", "-").replace("—", "-").replace("®", "").replace("™", "")
    h = re.sub(r"\s+", " ", h)
    h = re.sub(r"(\d)\s*\|\s*%", r"\1%", h)          # table cells '20 | %' -> '20%'
    h = re.sub(r"(\d) %", r"\1%", h)
    return h


PCT = r"(?:\d{1,3}(?:\.\d+)?\s*(?:%|percent\b|per cent\b)|\b(?:ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty)\s+percent\b)"
_PCT = re.compile(PCT, re.I)
_KEY = re.compile(r"(?i)\b(customers?|accounted for|represent(?:ed|s)?|sales to|revenues? from|net sales|"
                  r"revenues?|purchaser|distributor|retailer)\b")
_CUST = re.compile(r"(?i)\b(customers?|sales to|revenues? (?:from|to)|purchaser|largest|major|significant|"
                   r"accounted for)\b")
_SENT = re.compile(r"(?<=[a-z0-9\)%\"]\.)\s+(?=[A-Z\(\"\[])|(?<=;)\s+|\s+\|\s+\|\s+")

# capitalised name runs: 'Wal-Mart Stores, Inc.', 'The Home Depot', 'AmerisourceBergen Corporation', 'AT&T'
_NAME = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9\.\-'&]*|[A-Z]{2,}|&)"
    r"(?:(?:\s+|\s*,\s*(?=(?:Inc|Corp|Co|Ltd|LLC|L\.P|N\.V|plc|S\.A)\b))"
    r"(?:(?:of|and|the|de|du|la|&)\s+)?(?:[A-Z][A-Za-z0-9\.\-'&]*|&)){0,5})")

STOP_FIRST = set("""a an and as at by for from in into of on or our the to with we its it their this that these those
during fiscal year years sales net revenue revenues total customer customers company companies no one two three
each other all both approximately such including excluding item note notes see table accounts receivable
consolidated segment segments product products one's while also however additionally further in for approximately
""".split())
STOP_ANY = set("""january february march april may june july august september october november december
fiscal year years quarter quarters sales net revenue revenues total customer customers percent item note notes
table accounts receivable receivables consolidated segment segments company company's our we us gaap u.s. us
international domestic north south east west america americas europe asia pacific china japan canada mexico
""".split())
GENERIC = re.compile(r"(?i)^(the\s+)?(company|group|registrant|corporation|segment|business|division|"
                     r"government|federal|state|department|agency|medicare|medicaid|u\.?s\.?|united states|"
                     r"top|largest|major|significant|ten|five|three|two|one|customer [a-z0-9]|customer)\b")


def candidate_sentences(text: str, max_len: int = 700):
    """Yield sentences with a percentage and a customer keyword."""
    out = []
    for s in _SENT.split(text):
        s = s.strip()
        if len(s) < 25:
            continue
        if len(s) > max_len:
            # long table rows / run-ons: keep windows around the percentage
            for m in _PCT.finditer(s):
                w = s[max(0, m.start() - 300): m.end() + 120]
                if _CUST.search(w):
                    out.append(w)
            continue
        if _PCT.search(s) and _CUST.search(s) and _KEY.search(s):
            out.append(s)
    return out


def _clean_name(n: str) -> str:
    n = n.strip(" ,.;:'\"()-")
    n = re.sub(r"\s+", " ", n)
    return n


def _parts(n: str):
    """full run + its pieces split at ' and ' / ' & ' / ', ' (e.g. 'PepsiCo, Inc. and Wal-Mart Stores, Inc')."""
    out = [n]
    pieces = re.split(r"\s+and\s+|,\s+(?!(?:Inc|Corp|Co|Ltd|LLC|L\.P|N\.V|plc|S\.A)\b)", n)
    if len(pieces) > 1:
        out += [p for p in pieces if p and p[0].isupper()]
    return out


def candidate_names(sentence: str):
    names = []
    runs = []
    for m in _NAME.finditer(sentence):
        runs += _parts(_clean_name(m.group(1)))
    for n in runs:
        n = re.sub(r"'s$", "", _clean_name(n))
        toks = n.split()
        # strip leading stop words ('Sales to Walmart' -> 'Walmart' is handled by splitting on stop words)
        while toks and toks[0].lower().strip(".,") in STOP_FIRST:
            toks = toks[1:]
        if not toks:
            continue
        n = " ".join(toks).strip(" ,.;:'\"()-")
        if len(n) < 2 or not re.search(r"[A-Za-z]", n):
            continue
        low = n.lower()
        if all(t.lower().strip(".,'") in STOP_ANY or t.lower().strip(".,'") in STOP_FIRST for t in n.split()):
            continue
        if GENERIC.match(low):
            continue
        if re.fullmatch(r"[A-Z]\.?", n):
            continue
        names.append(n)
    # de-duplicate keeping order
    seen, res = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            res.append(n)
    return res


def extract(h: str):
    """HTML -> list of (sentence, [candidate names])."""
    t = html_to_text(h)
    res = []
    seen = set()
    for s in candidate_sentences(t):
        key = s[:200]
        if key in seen:
            continue
        seen.add(key)
        res.append((s, candidate_names(s)))
    return t, res
