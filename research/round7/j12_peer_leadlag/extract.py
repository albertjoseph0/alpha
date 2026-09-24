"""10-K HTML -> plain text -> Item 1 (Business), truncated, plus its competition passages.

html_to_text is copied from research/round6/j01_lazy_prices/extract.py (read-only reuse; copied so later edits there
cannot change these results). Item 1 is found with header regexes; the table of contents also matches, so we
take the (start, end) pair that gives the longest span (standard trick)."""
import html as htmlmod
import re

_BLOCK = re.compile(r"</?(p|div|br|tr|li|h[1-6]|table|center|font\s+[^>]*size)[^>]*>", re.I)
_TABLE = re.compile(r"<table.*?</table>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\xa0​]+")


def _is_numeric_table(t: str) -> bool:
    txt = htmlmod.unescape(_TAG.sub(" ", t))
    letters = sum(c.isalpha() for c in txt)
    digits = sum(c.isdigit() for c in txt)
    if letters < 300 and re.search(r"(?i)item\s*\d", txt):
        return False
    return digits > 0.15 * (letters + digits) or letters < 40


def html_to_text(h: str) -> str:
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
    out, prev_blank = [], False
    for ln in (x.strip() for x in h.split("\n")):
        if not ln:
            if not prev_blank:
                out.append("")
            prev_blank = True
        else:
            out.append(ln)
            prev_blank = False
    return "\n".join(out)


_I1 = re.compile(r"(?im)^\s*items?\s*1\s*(and\s*2\s*)?[\.\:\-—–]?\s*(\.|:)?\s*(business|description\s+of\s+business)?\b(?!\s*a)")
_I1E = re.compile(r"(?im)^\s*item\s*(1\s*a|1\s*b|2|3)\s*[\.\:\-—–]?\s*(risk|unresolved|properties|legal|cybersecurity)?")
_BUS = re.compile(r"(?im)^\s*(part\s+i\s*)?(item\s*1\.?\s*)?business\s*$")
_BUSE = re.compile(r"(?im)^\s*(item\s*(1\s*a|1\s*b|2|3)\b.*|risk\s+factors|properties|unresolved\s+staff\s+comments|legal\s+proceedings)\s*$")
_COMPH = re.compile(r"(?im)^\s*(industry\s+and\s+)?(competition|competitive\s+(environment|conditions|landscape|position|strengths)|competitors|our\s+competition|markets?\s+and\s+competition)\b[^\n]{0,60}$")
_RUNIN = re.compile(r"(?m)^\s*(Competition|Competitors)\s*[\.\:\-—–]\s")


def item1(text: str):
    """Return (item1_text, method)."""
    starts = [m.start() for m in _I1.finditer(text)]
    ends = [m.start() for m in _I1E.finditer(text)]
    best = (0, None)
    for s in starts:
        e = next((e for e in ends if e > s + 10), None)
        if e is not None and e - s > best[0]:
            best = (e - s, (s, e))
    if best[1] and best[0] >= 1500:
        s, e = best[1]
        body = text[s:e]
        return (body.split("\n", 1)[1] if "\n" in body else body).strip(), "item1"
    # fallback: a bare "Business" heading up to the next Item / Risk Factors / Properties heading (longest span)
    ends2 = [m.start() for m in _BUSE.finditer(text)]
    best = (0, None)
    for m in _BUS.finditer(text):
        e = next((e for e in ends2 if e > m.end()), len(text))
        if e - m.end() > best[0]:
            best = (e - m.end(), (m.end(), e))
    if best[1] and best[0] >= 1500:
        return text[best[1][0]:best[1][1]].strip(), "business_hdr"
    return "", "none"


def competition_text(it1: str, max_chars: int = 6000) -> str:
    """Competition subsection (heading or run-in) plus every sentence mentioning competitors elsewhere in Item 1."""
    parts = []
    m = _COMPH.search(it1) or _RUNIN.search(it1)
    if m:
        seg = it1[m.start(): m.start() + 4000]
        # stop at the next short heading-like line after a few paragraphs
        lines = seg.split("\n")
        keep, n = [], 0
        for i, ln in enumerate(lines):
            if i > 2 and 0 < len(ln) < 60 and not ln.endswith((".", ",", ";", ":")) and ln[:1].isupper() and n > 300:
                break
            keep.append(ln)
            n += len(ln)
        parts.append("\n".join(keep))
    for s in re.split(r"(?<=[\.\!\?])\s+", it1):
        if re.search(r"(?i)compet", s) and 30 < len(s) < 1200 and not any(s in p for p in parts):
            parts.append(s)
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n".join(parts)[:max_chars]
