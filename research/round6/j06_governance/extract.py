"""Proxy text -> Jev state: topic-quota paragraph selection + anonymization (company name, ticker, person
names, calendar years). Deterministic; used by s03_states.py and the leakage probe."""
import re

MAX_PARA = 1500
QUOTA = {"pay": 6000, "special": 3000, "sop": 2500, "rights": 5000, "board": 4500, "related": 3500, "policies": 5000}
TOPICS = {
    "pay": [r"performance[- ]based", r"at[- ]risk", r"pay mix|mix of pay|compensation mix", r"performance (share|stock|restricted stock) units?|\bPSUs?\b|performance shares",
            r"relative (total shareholder return|TSR)|\brTSR\b|relative to (the|our) (peer|s&p)", r"total shareholder return|\bTSR\b",
            r"performance (period|metric|measure|goal|cycle)s?", r"pay ?out|paid out|earned at|funded at", r"(%|percent) of target",
            r"long[- ]term incentive", r"annual (cash )?incentive|annual bonus|short[- ]term incentive", r"target (total direct )?compensation",
            r"restricted stock units?|\bRSUs?\b|stock options?|time[- ]based|time[- ]vest", r"pay[- ]for[- ]performance|pay and performance|align"],
    "special": [r"retention (award|grant|bonus|equity|rsu|incentive)", r"special (award|grant|equity|bonus|one[- ]time|retention|incentive|recognition)",
                r"one[- ]time", r"sign[- ]on|signing bonus|inducement", r"make[- ]whole|replacement award", r"(negative |positive |upward |its )?discretion",
                r"adjust(ed|ments?) (to|for)|excluded? the (impact|effect)", r"mega[- ]grant|front[- ]loaded|multi[- ]year grant"],
    "sop": [r"say[- ]on[- ]pay", r"advisory vote", r"votes? cast", r"\d{2}(\.\d+)? ?(%|percent)", r"shareholder (outreach|engagement|feedback)|stockholder (outreach|engagement|feedback)",
            r"support(ed)? (for )?(our|the) (executive )?compensation", r"in response to"],
    "rights": [r"classified board|staggered|three classes|declassif", r"annual(ly)? elect|elected annually|one-year term", r"supermajority|super-majority|two-thirds|66",
               r"rights (plan|agreement)|poison pill", r"dual[- ]class|class b common|votes per share|ten votes|voting power", r"proxy access",
               r"special meeting", r"written consent", r"majority vot(e|ing)|majority of (the )?votes cast", r"plurality", r"cumulative voting",
               r"controlled company", r"shareholder rights|stockholder rights"],
    "board": [r"independen", r"lead independent director|lead director|presiding director",
              r"chairman and chief executive|chair and chief executive|chairman and ceo|chair and ceo|chairman of the board and chief executive|combined|separat",
              r"other public (company )?boards?|public company (boards|directorships)|overboard|outside boards", r"tenure|retirement age|mandatory retirement|term limit",
              r"attend(ed|ance)", r"executive session", r"leadership structure"],
    "related": [r"related[- ]person|related[- ]party", r"transactions? with", r"immediate family|family member|brother|sister|\bson\b|daughter|spouse|in-law",
                r"employed by|employment of|is employed", r"lease[ds]? |purchas|\bpaid\b", r"aircraft", r"consulting (agreement|arrangement|fees)", r"\$\d"],
    "policies": [r"claw ?back|recoup", r"hedg", r"pledg", r"gross[- ]ups?", r"perquisites?|perks", r"personal use of", r"repric|exchange program|underwater",
                 r"single[- ]trigger|double[- ]trigger", r"change[- ]in[- ]control|change of control", r"stock ownership (guideline|requirement)|ownership guideline",
                 r"severance", r"tax (reimbursement|equalization)|excise tax", r"security (services|program|arrangements)|car (allowance|service)|club (dues|membership)"],
}
NEG = re.compile(r"broker non-vote|abstention|quorum|street name|record date|householding|revoke your proxy|vote by telephone", re.I)
CRX = {k: [re.compile(p, re.I) for p in v] for k, v in TOPICS.items()}


def paragraphs(text):
    out, pos = [], 0
    for chunk in re.split(r"\n\s*\n", text):
        start = text.find(chunk, pos)
        pos = start + len(chunk)
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) <= MAX_PARA:
            out.append((start, chunk))
            continue
        buf, bstart = "", start
        for ln in re.split(r"(?<=[.;:])\s+|\n", chunk):
            if len(buf) + len(ln) > MAX_PARA and buf:
                out.append((bstart, buf.strip()))
                bstart += len(buf)
                buf = ""
            buf += ln + " "
        if buf.strip():
            out.append((bstart, buf.strip()[:MAX_PARA * 2]))
    return out


def is_toc(p):
    lines = [ln for ln in p.split("\n") if ln.strip()]
    if len(lines) >= 3 and sum(bool(re.search(r"(\.{3,}|\s)\d{1,3}$", ln)) for ln in lines) / len(lines) > 0.4:
        return True
    return len(p) < 40


def select(text, quota=QUOTA):
    paras = paragraphs(text)
    chosen = {}
    for topic, rxs in CRX.items():
        scored = []
        for i, (st, p) in enumerate(paras):
            if is_toc(p):
                continue
            hits = [len(r.findall(p)) for r in rxs]
            nd = sum(h > 0 for h in hits)
            if nd == 0:
                continue
            s = nd + 0.1 * min(sum(hits), 10) - 2.0 * bool(NEG.search(p))
            if topic == "sop" and not re.search(r"say[- ]on[- ]pay|advisory vote", p, re.I):
                s -= 1.5
            if topic == "related" and not re.search(r"related[- ](person|party)|family|transaction", p, re.I):
                s -= 1.5
            scored.append((-s, i))
        scored.sort()
        used = 0
        for negs, i in scored:
            if -negs <= 0.5:
                break
            if i in chosen:
                continue
            L = len(paras[i][1])
            if used + L > quota[topic]:
                if used > quota[topic] * 0.8:
                    break
                continue
            chosen[i] = topic
            used += L
    idx = sorted(chosen)
    parts, last = [], -2
    for i in idx:
        if i != last + 1 and parts:
            parts.append("...")
        parts.append(paras[i][1])
        last = i
    return "\n".join(parts)


STOP = {"the", "inc", "corp", "corporation", "co", "company", "incorporated", "ltd", "limited", "plc", "holdings", "holding",
        "group", "de", "new", "nv", "n.v.", "sa", "ag", "lp", "llc", "trust", "international", "general", "american", "united",
        "national", "first", "southern", "western", "eastern", "northern", "public", "service", "services", "energy", "financial",
        "bancorp", "resources", "industries", "technologies", "systems", "communications", "entertainment", "brands", "products",
        "and", "&", "of", "a", "us", "u.s.", "global", "enterprises", "partners", "properties", "realty", "capital", "health",
        "healthcare", "insurance", "motors", "motor", "electric", "power", "gas", "oil", "data", "life", "stores", "foods", "food"}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def anonymize(state, full_text, company, ticker, year):
    """Replace the company's names, ticker, person names and calendar years (relative to the proxy year)."""
    names = set()
    base = re.sub(r"/[A-Z]{2,}/?", "", company or "").strip()
    base = re.sub(r"[,.]", " ", base)
    toks = [t for t in base.split() if t]
    core = [t for t in toks if t.lower() not in STOP]
    if toks:
        names.add(" ".join(toks))
    # full name without legal suffixes
    trimmed = list(toks)
    while trimmed and trimmed[-1].lower() in {"inc", "corp", "corporation", "co", "company", "incorporated", "ltd", "limited", "plc", "the", "nv", "sa", "ag", "llc", "lp"}:
        trimmed = trimmed[:-1]
    if trimmed:
        names.add(" ".join(trimmed))
    for t in core:
        if len(t) >= 4:
            names.add(t)
    # defined short names: (the "Xyz") / ("Xyz" or the "Company") in the first 40k chars
    for m in re.finditer(r"\(\s*(?:the\s+)?\"([A-Z][A-Za-z0-9&.\-' ]{1,40})\"", full_text[:40000]):
        cand = m.group(1).strip()
        if cand.lower() in {"company", "corporation", "board", "we", "us", "our", "proxy statement", "annual meeting", "meeting"}:
            continue
        if any(w.lower() in cand.lower() for w in core if len(w) >= 3):
            names.add(cand)
    out = state
    for n in sorted(names, key=len, reverse=True):
        if len(n) < 3:
            continue
        out = re.sub(r"(?<![A-Za-z])" + re.escape(n) + r"(?:'s)?(?![A-Za-z])", "the Company", out, flags=re.I if len(n) > 5 else 0)
    if ticker:
        tk = ticker.split("#")[0].replace("-", ".")
        if len(tk) >= 2:
            out = re.sub(r"(?<![A-Za-z])" + re.escape(tk) + r"(?![A-Za-z])", "[TICKER]", out)
    # person names: surnames seen after an honorific anywhere in the proxy
    sur = {}
    for m in re.finditer(r"\b(?:Mr|Ms|Mrs|Dr|Messrs)\.?\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-z'\-]+)?)", full_text):
        s = m.group(1).split()[-1]
        if len(s) >= 3 and s.lower() not in {"the", "and", "chairman", "chief"}:
            sur[s] = sur.get(s, 0) + 1
    order = sorted(sur, key=lambda s: -sur[s])
    for k, s in enumerate(order):
        tag = f"Person{k + 1}"
        out = re.sub(r"\b(?:[A-Z][a-z]+\.?\s+)?(?:[A-Z]\.\s+)?(?:\"[A-Z][a-z]+\"\s+)?" + re.escape(s) + r"(?:,? (?:Jr|Sr|III|II|IV)\.?)?\b", tag, out)
    # calendar years -> relative to the proxy year
    def yr(m):
        d = int(m.group(0)) - year
        return "[Y]" if d == 0 else f"[Y{d:+d}]"
    out = re.sub(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)", yr, out)
    out = re.sub(r"\b(" + MONTHS + r")\s+\d{1,2},", r"\1 [D],", out)
    return out
