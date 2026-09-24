"""Jev state preparation (Item 1.01 text, anonymised) and the frozen question list.
Changing anything here changes the request hash -> cache misses; the v1 list is FROZEN once DEV scoring starts."""
import re

from textutil import DATE_RE, one_line

ROLE = r"(?:the\s+)?\"?\s*(Company|Parent|Merger Sub|Purchaser|Buyer|Acquirer|Acquiror|Guarantor|Sponsor|Seller|Holdco|Topco|Merger Subsidiary|Offeror|Acquisition Sub|MergerCo|Target)\s*\"?"


def item101(t: str) -> str:
    """Item 1.01 section of an 8-K body (falls back to the text after the cover page)."""
    t1 = one_line(t)
    m = re.search(r"Item\s*1\.01\.?\s*Entry into a Material Definitive Agreement", t1, re.I)
    if not m:
        m = re.search(r"Item\s*1\.01", t1, re.I)
    if not m:
        m = re.search(r"Agreement and Plan of Merger", t1)
    start = m.start() if m else 0
    end_m = re.search(r"Item\s*(?:2\.0[1-6]|3\.0[1-3]|5\.0[1-8]|7\.01|8\.01|9\.01)\b", t1[start + 50:], re.I)
    end = start + 50 + end_m.start() if end_m else len(t1)
    sec = t1[start:end]
    if len(sec) < 1500 and end_m:   # Item 1.01 sometimes just refers to Item 8.01 / 2.03 text: keep more
        sec = t1[start:start + 40000]
    return sec


def anonymise(sec: str, names=()) -> str:
    s = sec
    # "Foo Holdings, Inc., a Delaware corporation (the "Company")" -> "the Company, a Delaware corporation"
    pat = re.compile(r"((?:[A-Z][\w.&'\-]*,?\s+){0,6}[A-Z][\w.&'\-]*)(,\s*(?:an?|the)\s[^()]{0,120}?)?\s*\(\s*" + ROLE + r"\s*\)")

    def rep(m):
        return f"the {m.group(3)}" + (m.group(2) or "")
    s = pat.sub(rep, s)
    for n in names:
        n = n.strip()
        if len(n) >= 4:
            core = re.sub(r"(?i)[,.]?\s*(inc|corp|corporation|co|company|ltd|llc|plc|lp|l\.p|holdings|group|n\.v|s\.a)\.?$", "", n).strip()
            for x in {n, core}:
                if len(x) >= 4:
                    s = re.sub(re.escape(x), "[name]", s, flags=re.I)
    s = re.sub(r"\((?:NYSE|NASDAQ|Nasdaq|AMEX|NYSE MKT|NYSE American)\s*:\s*[A-Z.]{1,6}\)", "", s)
    s = DATE_RE.sub("[date]", s)
    s = re.sub(r"\b(19|20)\d{2}\b", "[year]", s)
    return s


def state_for(t: str, names=(), maxc: int = 24000) -> str:
    return anonymise(item101(t), names)[:maxc]


YN = "noul"
QUESTIONS_V1 = {
    "financing_cond": {"type": YN, "instructions": "Does the text state that the buyer's obligation to complete the acquisition is conditioned on the buyer obtaining financing (a financing condition)?"},
    "debt_commit": {"type": YN, "instructions": "Does the text say the buyer has obtained debt financing commitments (commitment letters from banks or lenders) to fund the acquisition?"},
    "go_shop": {"type": YN, "instructions": "Does the agreement give the target a 'go-shop' period during which it may actively solicit alternative acquisition proposals?"},
    "reverse_fee": {"type": YN, "instructions": "Does the text say the buyer must pay the target a termination fee (a reverse termination fee) in some circumstances, for example a financing failure or a failure to obtain regulatory approval?"},
    "foreign_antitrust": {"type": YN, "instructions": "Are antitrust or competition approvals outside the United States (for example European Commission, China or other foreign merger control) listed as conditions to closing?"},
    "industry_reg": {"type": YN, "instructions": "Is approval from an industry regulator (for example bank regulators or the Federal Reserve, insurance commissioners, public utility commissions, FERC, FCC, gaming, or healthcare regulators) listed as a condition to closing?"},
    "cfius": {"type": YN, "instructions": "Is clearance by CFIUS (the Committee on Foreign Investment in the United States) or another national-security review listed as a condition to closing?"},
    "divestiture_commit": {"type": YN, "instructions": "Does the buyer commit to accept divestitures, remedies or other burdens (a 'hell or high water' type covenant) to obtain antitrust or regulatory approval?"},
    "approval_path": {"type": "choice", "instructions": "How will the target's shareholders approve or accept the deal according to the text?",
                      "criteria": {"tender_offer": None, "shareholder_vote": None, "written_consent": None, "not_stated": None}},
    "support_agmts": {"type": YN, "instructions": "Have directors, officers or large shareholders of the target signed agreements to vote for the deal or to tender their shares?"},
    "rival_bid": {"type": YN, "instructions": "Does the text mention a competing, unsolicited or rival acquisition proposal from another party, or an offer made without the agreement of the target's board?"},
    "buyer_type": {"type": "choice", "instructions": "What type of buyer is acquiring the target according to the text?",
                   "criteria": {"operating_company": None, "private_equity_or_financial_sponsor": None,
                                "insider_or_controlling_shareholder": None, "unclear": None}},
    "foreign_buyer": {"type": YN, "instructions": "Is the buyer (or its ultimate parent) described as organized or headquartered outside the United States?"},
    "minority_cond": {"type": YN, "instructions": "Is the deal conditioned on approval by a majority of the shares not held by the buyer, its affiliates or insiders (a majority-of-the-minority condition)?"},
    "cvr": {"type": YN, "instructions": "Does the consideration include a contingent value right (CVR) or another contingent or deferred payment in addition to the cash price?"},
    "stock_part": {"type": YN, "instructions": "Does the consideration paid to the target's shareholders include shares of the buyer's stock (so it is not all cash)?"},
    "litigation": {"type": YN, "instructions": "Does the text mention an existing lawsuit, government investigation or regulatory challenge involving the target or the transaction?"},
    "reg_complexity": {"type": "score", "instructions": "How complex and uncertain is the regulatory approval process described in the text?",
                       "criteria": ["simple or none", "moderate", "complex", "very complex"]},
}

LEAK_V1 = {
    "completed": {"type": YN, "instructions": "Was this acquisition ultimately completed (closed), rather than terminated or abandoned?"},
}
