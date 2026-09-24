"""Text cleaning shared by the dictionary baseline, Jev features and the leakage probe.

* body extraction (drop site navigation, release headers, footers)
* minutes: keep the policy discussion part (Committee/participants' discussion -> end), drop attendance
* anonymisation: dates, years, chair/member names and titles are removed (brief: strip names and dates)
* vote paragraphs are removed from the Jev state; dissents are counted in code instead
"""
import re

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.|Feb\.|Aug\.|Sept\.|Oct\.|Nov\.|Dec\.)"
CHAIRS = ["Greenspan", "Bernanke", "Yellen", "Powell", "Warsh", "Hassett", "Volcker"]


def statement_body(t: str) -> str:
    # start after the release header if present
    m = re.search(r"For (?:immediate )?release[^\n]*\n", t, re.I)
    if m:
        t = t[m.end():]
    # new-format pages: body begins with typical first words
    m = re.search(r"(Recent indicators|Information received|The Federal Open Market Committee|Chairman|The Federal Reserve|"
                  r"Economic activity|Although|Available indicators|The Committee|Indicators|Inflation|Uncertainty|"
                  r"The coronavirus|The ongoing|In light of|Over the past|Russia)", t)
    if m:
        t = t[m.start():]
    # cut footer
    end = re.search(r"\n\s*(Implementation Note issued|For media inquiries|\d{4} Monetary policy|Home \||Last Update|"
                    r"Board of Governors of the Federal Reserve System\s*\n|Related Information|Attachment)", t, re.I)
    if end:
        t = t[:end.start()]
    return t.strip()


def split_votes(t: str):
    """Return (text without vote paragraph, vote paragraph)."""
    pre = re.search(r"approved the following statement for release by an? (\d+)\s*[\u2013\u2014-]+\s*(\d+) vote:?", t)
    extra = ""
    if pre:   # 2026 format: vote tally in the preamble
        extra = f"TALLY {pre.group(1)}-{pre.group(2)}. "
        t = t[pre.end():].strip()
    m = re.search(r"(Voting for (?:the|this) (?:FOMC )?(?:monetary policy )?action|Voting for this action|Voting against (?:the|this) action)", t)
    if not m:
        return t, extra
    return t[:m.start()].strip(), extra + t[m.start():]


def count_dissents_statement(votes: str) -> int:
    tally = re.match(r"TALLY (\d+)-(\d+)", votes)
    if tally and "Voting against" not in votes:
        return int(tally.group(2))
    m = re.search(r"Voting against (?:the|this)?\s*(?:action|the action)?\s*(?:were|was)?:?(.*)", votes, re.S)
    if not m:
        return 0
    seg = m.group(1).split(".\n")[0]
    seg = re.split(r"(?<=[a-z]{3})\.\s", seg)[0]  # first sentence
    names = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][A-Za-z'\-]+", seg)
    return max(len(set(names)), 1)


def minutes_body(t: str) -> str:
    """Keep the policy discussion: from the Committee/participants' discussion to the end (minus notation votes)."""
    pats = [r"Participants' Views on Current Conditions", r"Participants. Views on Current", r"In (?:the Committee's|their) discussion",
            r"In the Committee's discussion", r"In their discussion of", r"Committee Policy Action",
            r"In the discussion of (?:current|the economic|monetary)", r"Participants agreed that"]
    starts = [m.start() for p in pats for m in [re.search(p, t)] if m]
    if starts:
        body = t[min(starts):]
    else:
        body = t[int(len(t) * 0.45):]
    end = re.search(r"\n\s*(Notation Vote|Adjournment|Secretary's note|It was agreed that the next meeting|Footnotes|"
                    r"Return to text|Last Update|\d{4} FOMC Meetings)", body)
    if end and end.start() > len(body) * 0.5:
        body = body[:end.start()]
    return body.strip()


def clean_minutes(body: str) -> str:
    body = re.sub(r"(?<!\n)\n(?!\n)", " ", body)          # join hard-wrapped lines
    body = re.sub(r"[ \t]+", " ", body)
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    keep = []
    for p in paras:
        if re.search(r"Votes? (?:for|against) (?:this|the|short-run)|voted as (?:an )?alternate|Voting (?:for|against) (?:this|the) action", p):
            continue
        keep.append(p.strip())
    return "\n\n".join(keep)[:60000]


def count_dissents_minutes(t: str) -> int:
    n = 0
    for m in re.finditer(r"(?:Votes?|Voting) against this action:\s*([^\n]*)", t):
        s = m.group(1)
        if re.match(r"\s*None", s):
            continue
        n = max(n, len(re.findall(r"(?:Mr|Ms|Mrs|Messrs|Mmes|Dr)\.|[A-Z][a-z]+(?:,|$| and)", s)) or 1)
    return n


SURNAMES = []   # filled by build_surnames() from the vote rolls / attendance lists of all raw documents
STOP = {"Federal", "Reserve", "Bank", "Board", "Committee", "Open", "Market", "Chair", "Chairman", "Vice", "Governor",
        "President", "Secretary", "Economist", "Manager", "System", "Account", "Deputy", "Associate", "Assistant",
        "Division", "Research", "Statistics", "Monetary", "Affairs", "International", "Finance", "Director", "General",
        "Counsel", "Senior", "Special", "Adviser", "Advisor", "Officer", "First", "Executive", "New", "York", "The",
        "United", "States", "Treasury", "Securities", "Street", "Policy", "Staff"}


def build_surnames(raw_texts):
    import collections
    c = collections.Counter()
    raw_texts = list(raw_texts)
    lower = collections.Counter(w for t in raw_texts for w in re.findall(r"\b[a-z]{3,}\b", t))
    pat = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)+\s+([A-Z][a-z]+(?:[A-Z][a-z]+)?)(?:,? Jr\.)?")
    pat2 = re.compile(r"\b(?:Messrs|Mr|Ms|Mrs|Mmes)\.\s+([A-Z][a-z]+)")
    for t in raw_texts:
        c.update(pat.findall(t))
        c.update(pat2.findall(t))
    names = sorted(n for n, k in c.items() if k >= 2 and n not in STOP and len(n) > 2 and lower[n.lower()] < 3)
    SURNAMES[:] = names
    return names


def anonymise(t: str) -> str:
    t = re.sub(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)+\s+[A-Z][A-Za-z'\-]+(?:,? Jr\.)?", "a member", t)
    t = re.sub(r"\b(?:Chairman|Chair|Vice Chairman|Vice Chair|Governor|President|Mr\.|Ms\.|Mrs\.|Dr\.|Messrs\.|Mmes\.)"
               r"(?:\s+[A-Z][A-Za-z'\-]+\.?){1,3}(?:(?:,\s*|\s+and\s+)(?:[A-Z][A-Za-z'\-]+\.?\s*){1,3})*",
               lambda m: "the Chair" if m.group(0).startswith("Chair") else "a member", t)
    for n in CHAIRS:
        t = re.sub(r"\b(?:[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?)?" + n + r"\b", "the Chair", t)
    if SURNAMES:
        t = re.sub(r"\b(?:[A-Z][a-z]+\s+)?(?:" + "|".join(SURNAMES) + r")\b", "a member", t)
    t = re.sub(MONTH + r"(?:\s+\d{1,2})?(?:,?\s+(?:19|20)\d{2})?", "[date]", t)
    t = re.sub(r"\b(?:19|20)\d{2}\b", "[year]", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()
