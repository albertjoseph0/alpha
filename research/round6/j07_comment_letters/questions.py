"""Jev question sets for j07 (SEC comment letters). Every set ever sent to Jev is listed here (log of trials).

Q_V1: the only feature set (frozen before TEST; see PREREG.md). Factual questions about what the letter says.
Q_LEAK: the forbidden outcome question, used only for the leakage probe on ~200 DEV letters.
State = 'Filing(s) reviewed: <form names>' + the redacted letter body (textprep.redact; company name, dates, years,
phone numbers, the address block and the signature block removed), capped at 20,000 characters.
"""

TOPICS = {
    "revenue_recognition": "how or when revenue is recognized (timing, gross vs net, multiple elements, ASC 605/606)",
    "non_gaap": "non-GAAP financial measures, their prominence, reconciliation or adjustments",
    "segment_reporting": "operating or reportable segments, segment aggregation, the chief operating decision maker",
    "impairment": "impairment or write-down of goodwill, intangible assets, long-lived assets or investments",
    "going_concern_or_liquidity": "going concern, liquidity, debt covenants, capital resources or funding needs",
    "disclosure_only_or_boilerplate": "routine requests to expand or clarify wording (MD&A narrative, risk factors, exhibits, "
                                      "legal or procedural items) that do not challenge any accounting",
    "other": "another accounting or reporting issue (income taxes, contingencies, business combinations, pensions, "
             "loan losses, reserves, etc.), or no substantive comment at all",
}

Q_V1 = {
    "topic": {"type": "choice",
              "instructions": "This is a letter from the SEC Division of Corporation Finance staff to a company about a filing "
                              "the staff reviewed. What is the main subject of the staff's comments in this letter?",
              "criteria": TOPICS},
    "severity": {"type": "score",
                 "instructions": "How serious are the staff's comments in this letter for the reliability of the company's "
                                 "reported financial statements?",
                 "criteria": ["none: no substantive comments, or only states that the review is complete",
                              "minor: small clarifications or disclosure tweaks in future filings",
                              "moderate: asks for expanded disclosure or supporting analysis, no challenge to the accounting",
                              "significant: questions an accounting policy, judgment or measurement and asks the company to justify it",
                              "severe: suggests reported figures may be wrong, or asks for restatement, amendment or error correction"]},
    "restate": {"type": "noul",
                "instructions": "Does the staff ask the company to restate its financial statements or to file an amended "
                                "report (for example a Form 10-K/A or 10-Q/A) now, rather than only revising disclosure in "
                                "future filings? Ignore generic boilerplate that mentions amendments."},
    "repeat": {"type": "noul",
               "instructions": "Does the letter repeat or reissue a comment from an earlier staff letter because the "
                               "company's previous response did not resolve it?"},
    "complete": {"type": "noul",
                 "instructions": "Is this letter only a notice that the staff has completed its review or has no further "
                                 "comments, with no new comments or requests?"},
}

Q_LEAK = {
    "outperform_12m": {"type": "noul",
                       "instructions": "Did this company's stock outperform the overall stock market over the 12 months "
                                       "after this letter was made public?"},
}

QUESTION_SETS_TRIED = {"v1": Q_V1, "leak": Q_LEAK}
STATE_CAP = 20000


def make_state(forms, body):
    fr = ", ".join(forms) if forms else "not stated"
    return f"Filing(s) reviewed: {fr}\n\n{body[:STATE_CAP]}"
