"""Letter cleaning, redaction (for Jev) and keyword-rule features (the no-LLM text baseline).

redact(): drops the address/'Re:' header (keeps only the NAMES of the forms reviewed), page headers, the closing
contact/signature block, and replaces the company name, dates, years, dollar-free file numbers and phone numbers.
"""
import re

MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.|Feb\.|Mar\.|Apr\.|Aug\.|Sept?\.|Oct\.|Nov\.|Dec\.)"
DATE_RE = re.compile(MONTHS + r"\s+\d{1,2},?\s+\d{4}", re.I)
YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]\d{3}-\d{4}")
FILE_RE = re.compile(r"File\s+No\.?:?\s*[\d-]+", re.I)
SUFFIX = re.compile(r"\b(inc|corp|corporation|co|company|ltd|plc|llc|lp|l\.p|n\.v|s\.a|ag|se|group|holdings?|trust|the)\b\.?", re.I)

FORM_PAT = re.compile(r"(Form\s+(?:10-K|10-Q|8-K|20-F|40-F|S-1|S-3|S-4|S-8|F-1|F-3|F-4|10-12B|10|11-K|DEF\s*14A|PRE\s*14A|PREM14A|DEFM14A|SC\s*TO-[IT]|SC\s*14D-?9|SC\s*13E-?3)(?:/A)?"
                      r"|Schedule\s+(?:14A|TO|13E-3|14D-9)|(?:Definitive|Preliminary)\s+Proxy\s+Statement|Registration\s+Statement)", re.I)


def split_header(text: str):
    """-> (header, body). Body starts after the salutation line ('Dear ...:')."""
    m = re.search(r"\n\s*Dear\s+[^\n]{1,80}[:,]\s*\n", text)
    if m and m.start() < 4000:
        return text[:m.start()], text[m.end():]
    m = re.search(r"\n\s*(Ladies and Gentlemen|To Whom)[^\n]{0,40}\n", text)
    if m and m.start() < 4000:
        return text[:m.start()], text[m.end():]
    return "", text


def forms_reviewed(header: str) -> list:
    out = []
    for f in FORM_PAT.findall(header):
        f = re.sub(r"\s+", " ", f.strip()).upper().replace("FORM ", "")
        if f not in out:
            out.append(f)
    return out


def form_class(forms: list) -> str:
    s = " ".join(forms)
    if re.search(r"\b(10-K|10-Q|20-F|40-F|8-K|11-K)\b", s) and not re.search(r"S-1|S-3|S-4|F-1|F-3|F-4|10-12B|REGISTRATION|14A|PROXY|SCHEDULE|SC ", s):
        return "periodic"
    if re.search(r"S-4|F-4|DEFM14A|PREM14A|SC TO|14D-9|13E-3|SCHEDULE TO", s):
        return "deal"
    if re.search(r"S-1|S-3|F-1|F-3|10-12B|REGISTRATION|S-8", s):
        return "registration"
    if re.search(r"14A|PROXY", s):
        return "proxy"
    if re.search(r"\b(10-K|10-Q|20-F|8-K)\b", s):
        return "periodic"
    return "other"


def cut_closing(body: str) -> str:
    m = re.search(r"\n\s*(You may contact|Please contact|Sincerely|If you have any questions|Please direct any questions)", body)
    return body[:m.start()] if m else body


def strip_page_headers(body: str) -> str:
    # 'Mr. X / Company / Date / Page 2' blocks inserted at page breaks
    body = re.sub(r"(?:\n[^\n]{0,80}){0,4}\n\s*Page\s+\d+\s*\n", "\n", body)
    return body


def company_regex(company: str):
    core = SUFFIX.sub(" ", company.replace("/", " ").replace(",", " "))
    core = re.sub(r"\b[A-Z]{2}\b$", "", core.strip())  # trailing state code like 'DE'
    words = [w for w in re.split(r"\s+", core) if len(w) > 1]
    if not words:
        return None
    pats = [r"\s+".join(map(re.escape, words))]
    if len(words[0]) >= 4:
        pats.append(re.escape(words[0]))
    return re.compile(r"\b(?:" + "|".join(pats) + r")\b[\w.,']*(?:\s+(?:Inc|Corp|Corporation|Company|Co|Ltd|plc|LLC)\b\.?)?", re.I)


BOILER = re.compile(r"^\s*(Please respond to (?:this|these|our)|After reviewing|We remind you|In closing|We urge all persons|"
                    r"Notwithstanding our comments|In responding to our comments|Please furnish a cover letter|"
                    r"Please understand that we may have|Please allow adequate time|We will consider a written request|"
                    r"Please refer to Rules? 460|Please be advised that you should not assume)", re.I)
INTRO_TAIL = re.compile(r"\s*(In some of our comments|Our comments ask you|In our comment|In our comments), we may ask you to provide us with "
                        r"information so we may better understand your disclosure\.", re.I)


def drop_boilerplate(body: str) -> str:
    paras = re.split(r"\n\s*\n", body)
    keep = [p for p in paras if not BOILER.match(p)]
    return INTRO_TAIL.sub("", "\n\n".join(keep))


def redact(text: str, company: str) -> dict:
    header, body = split_header(text)
    forms = forms_reviewed(header)
    body = drop_boilerplate(strip_page_headers(cut_closing(body)))
    cre = company_regex(company)
    if cre is not None:
        body = cre.sub("the Company", body)
    body = DATE_RE.sub("[DATE]", body)
    body = YEAR_RE.sub("[YEAR]", body)
    body = PHONE_RE.sub("[PHONE]", body)
    body = FILE_RE.sub("", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
    return {"forms": forms, "form_class": form_class(forms), "body": body}


KW = {
    "kw_rev": r"revenue recognition|recogni[sz]e[sd]? revenue|ASC 60[56]|Topic 60[56]|SAB 104|multiple[- ]element|principal (?:versus|vs\.?|or) agent|gross (?:versus|vs\.?) net|bill[- ]and[- ]hold|sell[- ]in|channel stuffing",
    "kw_nongaap": r"non-?GAAP|Item 10\(e\)|Regulation G|adjusted EBITDA|adjusted earnings|adjusted net income",
    "kw_segment": r"\bsegments?\b|ASC 280|chief operating decision maker|\bCODM\b|reportable segment|aggregat",
    "kw_impair": r"impairment|goodwill|ASC 350|ASC 360|reporting units?|write-?down",
    "kw_gc": r"going concern|substantial doubt|liquidity|covenant|capital resources|refinanc",
    "kw_restate": r"restate|restatement|amend (?:your|the) (?:Form|filing)|amended (?:Form|filing|10-K)|file an amendment|10-K/A|10-Q/A|Item 4\.02|non-reliance|material weakness|error correction|correction of an error",
    "kw_repeat": r"prior comment|previous comment|reissue|we note your response|your response to (?:our )?(?:prior )?comment|response letter dated|still (?:not )?(?:clear|unclear)",
    "kw_complete": r"completed our review|no further comments",
    "kw_future": r"in future filings",
    "kw_tellus": r"please tell us|please explain|please provide us|please provide (?:your|an) analysis|tell us how|tell us why",
    "kw_loss": r"loss contingenc|litigation|investigation|subpoena|SEC enforcement|DOJ",
    "kw_tax": r"income tax|valuation allowance|uncertain tax|repatriat",
}
KW_RE = {k: re.compile(v, re.I) for k, v in KW.items()}


def keyword_features(body: str) -> dict:
    f = {k: len(r.findall(body)) for k, r in KW_RE.items()}
    nums = [int(x) for x in re.findall(r"(?m)^\s*(\d{1,2})\.\s", body)]
    f["n_comments"] = max(nums) if nums else 0
    f["n_words"] = len(body.split())
    return f
