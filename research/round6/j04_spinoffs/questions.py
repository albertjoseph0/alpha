"""Frozen Jev question set (v1). Factual questions about what the information statement says.
Any change must be logged in STATUS.md / README.md (question-set log)."""

QSET_VERSION = "v1"

QUESTIONS = {
    "reason": {"type": "choice",
               "instructions": "According to the text, what is the MAIN stated reason for separating SpinCo from Parent?",
               "criteria": {"strategic_focus": "each company can focus on its own strategy, markets, capital allocation or valuation",
                            "activist_pressure": "the separation responds to shareholder or activist investor pressure",
                            "regulatory": "regulatory, legal or antitrust requirements or constraints",
                            "tax": "tax efficiency or a tax-driven structure (e.g. REIT conversion)",
                            "separate_underperforming_unit": "separating a weaker, slower-growing, troubled or non-core unit from the parent"}},
    "mgmt_grants": {"type": "noul",
                    "instructions": "Does the text state that SpinCo's executives will receive significant NEW equity awards in connection "
                                    "with the separation (for example founders' grants, special one-time, launch or retention equity grants), "
                                    "beyond merely converting or adjusting existing Parent awards?"},
    "debt_to_parent": {"type": "noul",
                       "instructions": "Does the text state that SpinCo will incur new debt (loans or notes) and use the proceeds to pay a "
                                       "cash distribution, dividend or other cash payment to Parent in connection with the separation?"},
    "diff_industry": {"type": "noul",
                      "instructions": "Based on the business descriptions in the text, does SpinCo operate in a different industry from "
                                      "Parent's remaining businesses?"},
    "parent_stake": {"type": "noul",
                     "instructions": "Does the text state that Parent will retain an ownership stake in SpinCo's common stock after the distribution?"},
    "pays_dividend": {"type": "noul",
                      "instructions": "Does the text state that SpinCo intends to pay a regular cash dividend after the distribution?"},
    "leverage": {"type": "score",
                 "instructions": "How much debt does the text say SpinCo will carry after the separation, relative to the size of its business?",
                 "criteria": ["no debt", "little debt", "moderate debt", "substantial debt", "very heavy debt"]},
}

# Forbidden (leakage probe) question: asked separately on ~200 DEV documents, never used as a feature.
PROBE = {"outperf": {"type": "noul",
                     "instructions": "Did this company's stock outperform the overall stock market over the 12 months after it began trading?"}}

TOPIC_ORDER = ["business", "reasons", "equity", "financing", "dividend", "stake"]


def state_from_sections(sec: dict, max_chars: int = 40000) -> str:
    parts, used = [], 0
    for k in TOPIC_ORDER:
        for w in sec.get(k, []):
            if used + len(w) > max_chars:
                w = w[: max(0, max_chars - used)]
            if not w:
                break
            parts.append(f"[{k.upper()} EXCERPT]\n{w}")
            used += len(w)
    return ("Excerpts from a Form 10 information statement for a corporate spin-off. 'SpinCo' is the company being spun off; "
            "'Parent' is the company distributing its shares.\n\n" + "\n\n".join(parts))
