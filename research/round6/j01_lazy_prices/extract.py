"""10-K / 10-Q HTML -> plain text -> sections (Risk Factors, MD&A, Legal Proceedings).

Items are found with header regexes; the table of contents also matches, so for each section we take the
(start, end) pair that gives the longest span (standard trick). Tables are dropped (numbers are kept in code,
not text), which also keeps MD&A to its narrative."""
import html as htmlmod
import re

_BLOCK = re.compile(r"</?(p|div|br|tr|li|h[1-6]|table|center|font\s+[^>]*size)[^>]*>", re.I)
_TABLE = re.compile(r"<table.*?</table>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t  ​]+")


def _is_numeric_table(t: str) -> bool:
    txt = _TAG.sub(" ", t)
    txt = htmlmod.unescape(txt)
    letters = sum(c.isalpha() for c in txt)
    digits = sum(c.isdigit() for c in txt)
    # keep text-heavy "tables" (some filers lay out paragraphs / item headers in tables)
    if letters < 300 and re.search(r"(?i)item\s*\d", txt):
        return False
    return digits > 0.15 * (letters + digits) or letters < 40


def html_to_text(h: str) -> str:
    # only the first <DOCUMENT> if a full submission was passed
    m = re.search(r"<DOCUMENT>.*?</DOCUMENT>", h, re.S)
    if m:
        h = m.group(0)
    h = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", h, flags=re.I | re.S)
    h = re.sub(r"<ix:header>.*?</ix:header>", " ", h, flags=re.I | re.S)
    h = _TABLE.sub(lambda m: "\n" if _is_numeric_table(m.group(0)) else
                   _BLOCK.sub("\n", m.group(0)).replace("</td>", " ").replace("</TD>", " "), h)
    h = _BLOCK.sub("\n", h)
    h = _TAG.sub("", h)
    h = htmlmod.unescape(h)
    h = _WS.sub(" ", h)
    lines = [ln.strip() for ln in h.split("\n")]
    out, prev_blank = [], False
    for ln in lines:
        if not ln:
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            out.append(ln)
            prev_blank = False
    return "\n".join(out)


def _hdr(pat):
    # "Item 1A." at the start of a line, optionally followed by a title on the same or next line
    return re.compile(r"(?im)^\s*item\s*" + pat)


H10K = {
    "rf": (_hdr(r"1\s*a\s*[\.\:\-—–]?\s*(risk\s+factors)?"),
           _hdr(r"(1\s*b|2)\s*[\.\:\-—–]?\s*(unresolved|properties|cybersecurity)?")),
    "mda": (_hdr(r"7\s*[\.\:\-—–]?\s*(management|md&a)"),
            _hdr(r"(7\s*a|8)\s*[\.\:\-—–]?\s*(quantitative|financial\s+statements|consolidated)?")),
    "legal": (_hdr(r"3\s*[\.\:\-—–]?\s*legal\s+proceedings"),
              _hdr(r"(4|4a)\s*[\.\:\-—–]?\s*(mine|submission|\(?removed|\[?reserved|executive)?")),
}
H10Q = {
    "mda": (_hdr(r"2\s*[\.\:\-—–]?\s*(management|md&a)"),
            _hdr(r"(3|4)\s*[\.\:\-—–]?\s*(quantitative|controls)")),
    "rf": (_hdr(r"1\s*a\s*[\.\:\-—–]?\s*(risk\s+factors)?"),
           _hdr(r"(2|3|4|5|6)\s*[\.\:\-—–]?\s*(unregistered|defaults|mine|other|exhibits|issuer)")),
    "legal": (_hdr(r"1\s*[\.\:\-—–]?\s*legal\s+proceedings"),
              _hdr(r"1\s*a\s*[\.\:\-—–]?|(2)\s*[\.\:\-—–]?\s*(unregistered|changes)")),
}
MIN_LEN = {"rf": 400, "mda": 1500, "legal": 60}


def extract_sections(text: str, form: str) -> dict:
    pats = H10K if form.startswith("10-K") else H10Q
    out = {}
    for sec, (sp, ep) in pats.items():
        starts = [m.start() for m in sp.finditer(text)]
        ends = [m.start() for m in ep.finditer(text)]
        best = (0, None)
        for s in starts:
            e = next((e for e in ends if e > s + 20), None)
            if e is None:
                continue
            if e - s > best[0]:
                best = (e - s, (s, e))
        if best[1] and best[0] >= MIN_LEN[sec]:
            s, e = best[1]
            body = text[s:e]
            body = body.split("\n", 1)[1] if "\n" in body else body  # drop header line
            out[sec] = body.strip()
    return out


_JUNK = re.compile(r"(?i)(table of contents|index|page \d+|\d+|[ivx]+|part [iv]+|\(?continued\)?|.{0,60}\|\s*\d+)")


def paragraphs(sec_text: str, min_chars: int = 40):
    """Split into paragraphs; drop page headers/footers; re-join paragraphs broken by page breaks
    (a chunk starting in lower case continues the previous one)."""
    chunks = []
    for p in re.split(r"\n\s*\n", sec_text):
        p = " ".join(p.split())
        if not p or _JUNK.fullmatch(p):
            continue
        if chunks and (p[0].islower() or (chunks[-1][-1] not in '.:;?!"\u201d)' and p[0].isalpha()
                                          and len(chunks[-1]) > 80 and chunks[-1][-1].isalpha())):
            chunks[-1] = chunks[-1] + " " + p
        else:
            chunks.append(p)
    return [p for p in chunks if len(p) >= min_chars]
