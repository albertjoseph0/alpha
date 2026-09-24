"""Company-name normalisation, the pool name index, capitalised-name extraction from competition passages,
name stripping for Jev states, and short name-free business descriptions."""
import re

SUFFIX = {"inc", "incorporated", "corp", "corporation", "co", "company", "companies", "ltd", "limited", "plc", "llc",
          "lp", "l", "p", "holdings", "holding", "group", "nv", "n", "v", "sa", "ag", "se", "the", "de", "new", "trust",
          "cos", "hldgs", "intl", "del", "md", "ny", "pa", "oh", "nj", "va", "ma", "tx", "ca", "fl", "mn", "wi", "ga",
          "in", "mo", "co", "ltd", "adr", "reit", "class", "a", "b"}
GENERIC_TAIL = {"stores", "industries", "enterprises", "technologies", "technology", "systems", "international",
                "worldwide", "brands", "financial", "resources", "services", "partners", "properties", "labs",
                "laboratories", "pharmaceuticals", "therapeutics", "communications", "entertainment", "energy", "global",
                "solutions", "products", "and"}
COMMON = {"general", "first", "american", "national", "united", "southern", "northern", "western", "eastern", "central",
          "international", "global", "standard", "universal", "public", "capital", "energy", "health", "service",
          "services", "data", "community", "pacific", "atlantic", "great", "best", "home", "new", "royal", "advanced",
          "applied", "digital", "old", "main", "state", "federal", "republic", "texas", "carolina", "boston", "state",
          "progressive", "equity", "alliance", "summit", "pioneer", "discovery", "frontier", "liberty", "patriot",
          "premier", "prime", "select", "superior", "valley", "west", "east", "north", "south", "one", "live", "target",
          "gap", "ball", "visa", "square", "block", "meta", "match", "crown", "chemical", "marine", "mobile", "wireless",
          "cooper", "graham", "owens", "harris", "hill", "church", "stanley", "hunt", "watts", "hess", "mason", "news"}


def core(name: str) -> str:
    s = name.lower()
    s = re.sub(r"/[a-z]{2,4}/?", " ", s)
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    t = s.split()
    while t and t[0] == "the":
        t = t[1:]
    while t and t[-1] in SUFFIX:
        t = t[:-1]
    return " ".join(t)


def variants(name: str) -> set:
    c = core(name)
    out = set()
    if not c:
        return out
    t = c.split()
    cands = {c}
    tt = list(t)
    while len(tt) > 1 and tt[-1] in GENERIC_TAIL:
        tt = tt[:-1]
        cands.add(" ".join(tt))
    for v in list(cands):
        vt = v.split()
        if len(vt) == 2 and all(len(x) <= 5 for x in vt):
            cands.add("".join(vt))          # wal mart -> walmart
    for v in cands:
        vt = v.split()
        if len(vt) == 1 and (len(v) < 4 or v in COMMON or v.isdigit()):
            continue
        if len(vt) >= 2 and all(x in COMMON or x in GENERIC_TAIL or len(x) < 3 for x in vt):
            continue
        out.add(v)
    return out


def build_index(firms: dict) -> dict:
    """firms: cik -> list of names (current + former). Returns variant -> set(cik)."""
    idx = {}
    for cik, names in firms.items():
        for n in names:
            for v in variants(n):
                idx.setdefault(v, set()).add(cik)
    return idx


_CAP = re.compile(r"(?:[A-Z][\w'’\.\-]*|&)(?:[ \t]+(?:[A-Z][\w'’\.\-]*|&|and|of|de))*")


def cap_phrases(text: str):
    return [m.group(0) for m in _CAP.finditer(text)]


def named_ciks(comp_text: str, index: dict, maxlen: int = 5) -> dict:
    """Capitalised phrases in the competition passages -> pool CIKs they name. Returns cik -> matched string."""
    found = {}
    for ph in cap_phrases(comp_text):
        toks = core(ph).split() if len(ph) < 120 else []
        n = len(toks)
        for i in range(n):
            for j in range(min(n, i + maxlen), i, -1):
                v = " ".join(toks[i:j])
                if v in index:
                    for c in index[v]:
                        found.setdefault(c, v)
                    break
    return found


_SUFFIX_NAME = re.compile(r"\b(?:[A-Z][\w'’\.\-&]*[ \t]+){0,4}[A-Z][\w'’\.\-&]*,?[ \t]+"
                          r"(?:Inc|Corp|Corporation|Company|Co|Ltd|LLC|plc|PLC|N\.V|S\.A|AG|L\.P|Holdings|Group)\b\.?")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_MONTHDATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
                        r"\s+\d{1,2}(,\s*)?")


def strip_names(text: str, own: set, index: dict, own_ticker: str = None) -> str:
    """Remove the firm's own names (-> 'the Company'), other pool-firm names and '<Name> Inc.' patterns
    (-> 'another company'), exact dates and years."""
    s = _SUFFIX_NAME.sub(lambda m: "another company", text)
    # longest-first replacement of name variants found as capitalised phrases
    def rep(m):
        ph = m.group(0)
        toks = core(ph).split()
        if not toks:
            return ph
        v = " ".join(toks)
        for n in range(len(toks), 0, -1):
            for i in range(0, len(toks) - n + 1):
                w = " ".join(toks[i:i + n])
                if w in own:
                    return "the Company"
                if w in index:
                    return "another company"
        return ph
    s = _CAP.sub(rep, s)
    if own_ticker:
        s = re.sub(r"\b" + re.escape(own_ticker) + r"\b", "the Company", s)
    s = _MONTHDATE.sub("", s)
    s = _YEAR.sub("[year]", s)
    return s


_VERB = re.compile(r"(?i)\b(provides?|provider|manufactur\w*|designs?|develops?|operates?|offers?|sells?|engaged|"
                   r"produces?|distributes?|markets?|owns?|leading|leader|supplier|retailer|bank|insurer|"
                   r"serves?|delivers?|explor\w*|generat\w*|transmi\w*|invests?)\b")
_BAD = re.compile(r"(?i)(incorporated in|headquarter|website|www\.|annual report|forward-looking|securities and exchange|"
                  r"form 10-k|as used in this|refer to|unless the context|fiscal year|we were founded|was founded|"
                  r"principal executive offices|table of contents|this report|internet address)")


def description(item1_text: str, max_chars: int = 330) -> str:
    head = item1_text[:8000]
    sents = [" ".join(x.split()) for x in re.split(r"(?<=[\.\!\?])\s+|\n+", head)]
    sents = [x for x in sents if 40 <= len(x) <= 600 and not _BAD.search(x)]
    good = [x for x in sents if _VERB.search(x)]
    pick = (good or sents)[:3]
    out = ""
    for x in pick:
        if len(out) + len(x) > max_chars and out:
            break
        out = (out + " " + x).strip()
    return out[:max_chars + 150]
