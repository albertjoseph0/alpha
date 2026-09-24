"""Regex/metadata extraction from Form 10 information statements (no LLM). Used by 02_extract.py and the
keyword baseline. Everything here reads only the text of the document itself (known before trading)."""
import gzip
import re
from collections import Counter

D = "/home/user/alpha/data/round6/j04_spinoffs"

WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
           "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
           "fifty": 50, "thirteen": 13, "fourteen": 14, "sixteen": 16, "eighteen": 18, "twenty-five": 25, "a": 1, "an": 1, "half": 0.5}


def load(cik):
    with gzip.open(f"{D}/text/{cik}.txt.gz", "rt") as f:
        raw = f.read()
    flat = re.sub(r"\s+", " ", raw)
    flat = flat.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return flat


SYM = re.compile(r"under the (?:trading |ticker )?symbols? \"?'?([A-Z][A-Z0-9]{0,5}(?:[.\-][A-Z]{1,2})?)")
LIST_INTENT = re.compile(r"(appl(?:y|ied|ication)|approv|admitted|authoriz|expect|intend|anticipat|will be listed|will trade|"
                         r"to be listed|will be traded|will begin trading|has been listed|have been listed|to list)", re.I)
EXCH = [("NYSE", re.compile(r"New York Stock Exchange|NYSE(?! (?:MKT|Amex|American|Arca))", re.I)),
        ("NASDAQ", re.compile(r"nasdaq", re.I)),
        ("AMEX", re.compile(r"American Stock Exchange|NYSE (?:MKT|Amex|American)|AMEX", re.I)),
        ("OTC", re.compile(r"OTC|Over-the-Counter|Pink Sheets|Bulletin Board|pink", re.I))]


def exchange(ctx):
    for name, rx in EXCH:
        if rx.search(ctx):
            return name
    return None


def tickers(flat, name_word):
    """Return (spin_ticker, spin_exchange, parent_ticker, parent_exchange, n_spin_candidates)."""
    spin, other = Counter(), Counter()
    exch = {}
    for m in SYM.finditer(flat):
        t = m.group(1).rstrip(".")
        if t in {"I", "A", "THE", "OF"}:
            continue
        ctx = flat[max(0, m.start() - 260): m.start()]
        ex = exchange(ctx) or exchange(flat[m.start(): m.start() + 60])
        exch.setdefault(t, Counter())[ex] += 1
        own = re.search(r"\b(our|we|us)\b", ctx[-200:], re.I) or (name_word and name_word.lower() in ctx[-200:].lower())
        if LIST_INTENT.search(ctx[-220:]) and own:
            spin[t] += 2
        elif own and not re.search(r"continue", ctx[-150:], re.I):
            spin[t] += 1
        else:
            other[t] += 1
    st = spin.most_common(1)[0][0] if spin else None
    pt = None
    for t, _ in other.most_common():
        if t != st:
            pt = t
            break
    se = exch[st].most_common(1)[0][0] if st else None
    pe = exch[pt].most_common(1)[0][0] if pt else None
    return st, se, pt, pe, len(spin)


def num(s):
    s = s.lower().replace(",", "")
    if s in WORDNUM:
        return float(WORDNUM[s])
    try:
        return float(s)
    except ValueError:
        return None


NUMW = r"(\d[\d,]*(?:\.\d+)?|\.\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|eighteen|twenty|twenty-five|thirty|forty|fifty|a|an)"
R1 = re.compile(NUMW + r" (?:shares?|common shares?) of [A-Za-z0-9'.&\- ]{0,40}?(?:common stock|common shares?|stock)?,? ?(?:\w+ ){0,3}?for (?:every|each) "
                r"(?:" + NUMW + r" )?(?:\([^)]{0,12}\) )?(?:[A-Za-z0-9'.&\- ]{0,40}? )?(?:shares?|common shares?|voting shares?)", re.I)
R2 = re.compile(r"(?:ratio of|distribution ratio (?:of|is|will be)) " + NUMW + r" (?:shares? )?(?:of [\w ]{0,30}?)?(?:for|per) (?:every|each)? ?(?:" + NUMW + r" )?(?:shares?)", re.I)


def ratio(flat):
    """SpinCo shares received per parent share."""
    vals = []
    for rx in (R1, R2):
        for m in rx.finditer(flat):
            a = num(m.group(1)); b = num(m.group(2)) if m.group(2) else 1.0
            if a and b:
                vals.append(a / b)
    vals = [v for v in vals if 1e-4 < v < 50]
    if not vals:
        return None, 0
    c = Counter(round(v, 6) for v in vals)
    return c.most_common(1)[0][0], len(vals)


SH = re.compile(r"approximately " + r"(\d[\d,]*(?:\.\d+)?) (million |billion )?(?:shares of (?:our )?common stock|of our shares|common shares)"
                r"[^.]{0,80}?(?:outstanding|issued|distributed)", re.I)


def shares_out(flat):
    vals = []
    for m in SH.finditer(flat):
        v = num(m.group(1))
        if v is None:
            continue
        if m.group(2):
            v *= 1e6 if "million" in m.group(2).lower() else 1e9
        if 1e5 < v < 1e10:
            vals.append(v)
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def is_spinoff_doc(flat):
    f = flat.lower()
    return ("information statement" in f and "distribution" in f and
            bool(re.search(r"no (?:established )?public (?:trading )?market|when-issued|regular-way", f)))


PARENT_RX = [re.compile(r"(?:wholly[- ]owned subsidiary of|separation from|spin-?off (?:of us )?from|distribution by|"
                        r"subsidiary of|separate us from) ([A-Z][A-Za-z0-9&'\-]+(?: [A-Z][A-Za-z0-9&'\-]+){0,3})"),
             re.compile(r"([A-Z][A-Za-z0-9&'\-]+(?: [A-Z][A-Za-z0-9&'\-]+){0,3}) (?:will|intends to|plans to) distribute "
                        r"(?:all|approximately|\d)")]
STOP = {"The", "Our", "We", "This", "Inc", "Corporation", "Company", "Holdings", "In", "A", "An", "Its", "Such", "Each",
        "After", "Following", "Prior", "Upon", "If", "As", "Board", "Directors"}


def parent_name(flat, own_name):
    c = Counter()
    for rx in PARENT_RX:
        for m in rx.finditer(flat[:400000]):
            w = m.group(1).split()
            w = [x for x in w if x not in STOP]
            if not w:
                continue
            key = re.sub(r"(?:'s|')$", "", w[0]).rstrip(",.")
            if len(key) < 2 or (own_name and key.lower() == own_name.lower()):
                continue
            c[key] += 1
    return c.most_common(1)[0][0] if c else None


def name_word(edgar_name):
    w = [x for x in re.sub(r"[^A-Za-z0-9&' ]", " ", edgar_name.split("(")[0]).split()
         if x.upper() not in {"INC", "CORP", "CO", "THE", "LTD", "LLC", "HOLDINGS", "HOLDING", "CORPORATION", "COMPANY",
                              "GROUP", "NEW", "SPINCO", "PLC", "LP", "N.V", "NV"}]
    return w[0] if w else None


# ---------------------------------------------------------------- anonymisation and section windows
DEF_SPIN = re.compile(r"\"([A-Z][A-Za-z0-9&.\-]+(?: [A-Z][A-Za-z0-9&.\-]+){0,2}),?\" (?:\"we,\"|\"us,\"|\"our,\"|\"the Company,\")")


def aliases(flat, nw, pname, extra_tickers):
    spin = set()
    if nw and len(nw) > 2:
        spin.add(nw)
    for m in DEF_SPIN.finditer(flat[:300000]):
        spin.add(m.group(1))
    par = {pname} if pname and len(pname) > 2 else set()
    par -= spin
    return spin, par


def anonymise(text, spin, par, tickers):
    for a in sorted(spin, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(a) + r"\b", "SpinCo", text, flags=re.I)
    for a in sorted(par, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(a) + r"\b", "Parent", text, flags=re.I)
    for t in tickers:
        if t and len(t) >= 2:
            text = re.sub(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", "[TICKER]", text)
    text = re.sub(r"\b(19[5-9]\d|20[0-3]\d)\b", "[YEAR]", text)
    return text


TOPICS = {
    "business": ([r"\bSpinCo is (?:a|an|one of the|the) ", r"\bwe are (?:a|an|one of the|the) (?:leading|global|premier|diversified|provider|[a-z]+)",
                  r"\bParent is (?:a|an|one of the|the) ", r"Parent'?s? (?:remaining|other|retained) business"], 1500, 6000),
    "reasons": ([r"reasons? for the (?:distribution|spin-?offs?|separations?)", r"purposes? of the (?:distribution|spin-?off|separation)",
                 r"background (?:of|to) the (?:distribution|spin-?off|separation)", r"benefits of the (?:distribution|spin-?off|separation)"], 3000, 9000),
    "equity": ([r"treatment of (?:outstanding )?(?:equity|stock|long-term incentive|share-based|stock-based|options)",
                r"(?:founders?|retention|make-whole|special|one-time|sign-on|inducement|initial|spin-?off|separation|launch)[- ](?:equity |stock |option |RSU |restricted stock |performance )?(?:grants?|awards?)",
                r"in connection with the (?:distribution|spin-?off|separation)[^.]{0,120}(?:grant|award)"], 1600, 8000),
    "financing": ([r"(?:cash )?(?:distribution|dividend|payment|transfer)s? (?:of [^.]{0,60})?to Parent", r"incur[^.]{0,80}indebtedness",
                   r"description of (?:material |certain )?indebtedness", r"financing (?:arrangements|transactions)",
                   r"special (?:cash )?(?:dividend|distribution|payment)", r"(?:new|senior) (?:secured )?(?:credit facility|notes|term loan)"], 1600, 8000),
    "dividend": ([r"dividend policy"], 1200, 3000),
    "stake": ([r"retain[^.]{0,120}(?:%|percent)", r"will (?:no longer|not) own", r"Parent will own", r"(?:after|following) the (?:distribution|spin-?off|separation)[^.]{0,80}(?:will|would) (?:own|hold|retain)"], 1200, 4000),
}


def windows(text, pats, width, budget):
    spans = []
    for p in pats:
        for m in re.finditer(p, text, re.I):
            spans.append((max(0, m.start() - 150), min(len(text), m.start() + width)))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    # skip table-of-contents style windows (few sentence ends) and duplicates; longest-content first order kept
    out, seen, used = [], set(), 0
    for s, e in merged:
        w = text[s:e]
        if w.count(". ") < 4:
            continue
        key = re.sub(r"\W", "", w[150:450]).lower()
        if key in seen:
            continue
        seen.add(key)
        if used + len(w) > budget:
            w = w[: max(0, budget - used)]
        if len(w) < 300:
            break
        out.append(w)
        used += len(w)
    return out


def sections(anon):
    return {k: windows(anon, *v) for k, v in TOPICS.items()}
