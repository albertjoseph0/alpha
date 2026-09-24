"""Jev question sets (logged; each version is frozen once used). Factual questions about the filing's text only."""

Q_V1 = {
    "category": {"type": "choice", "instructions": "Which category best describes the main event disclosed in this filing?",
                 "criteria": {
                     "debt_financing": "notes offering, credit facility, loan agreement, debt redemption or refinancing",
                     "equity_issuance": "sale of common stock, convertible securities or an at-the-market program",
                     "buyback_or_dividend": "share repurchase authorization or program, special or increased dividend",
                     "acquisition_by_company": "the company agrees to buy or has bought a business or assets",
                     "divestiture_or_spinoff": "the company sells, spins off or separates a business or assets",
                     "company_being_acquired": "the company itself agrees to be acquired or merged into another company",
                     "executive_change": "departure or appointment of an executive officer",
                     "board_change": "departure or appointment of a director",
                     "compensation_or_governance": "pay plans, employment agreements, bylaws, shareholder meeting matters",
                     "commercial_contract": "customer, supply, partnership, licensing or collaboration agreement",
                     "restructuring_or_impairment": "layoffs, restructuring, closures, write-downs or impairments",
                     "legal_or_regulatory": "litigation, settlement, investigation, government or regulatory action",
                     "product_or_approval": "product launch, regulatory approval, clinical or technical results",
                     "business_update_or_guidance": "operating update, outlook or guidance, investor presentation",
                     "accounting_or_listing": "auditor change, restatement, non-reliance, delisting or listing notice",
                     "other": "anything else"}},
    "tone": {"type": "score", "instructions": "Based only on what the filing states, how favorable is the disclosed news for the company's shareholders?",
             "criteria": ["clearly unfavorable", "somewhat unfavorable", "neutral or routine", "somewhat favorable", "clearly favorable"]},
    "magnitude": {"type": "score", "instructions": "How large is the disclosed event relative to the size of the company's overall business, as described in the filing?",
                  "criteria": ["immaterial or routine", "small", "moderate", "large", "transformative"]},
    "routine": {"type": "noul", "instructions": "Is this a routine or administrative disclosure (for example a standard debt issuance or refinancing, a regular dividend, shareholder-meeting or bylaw matters, compensation plan terms, or an investor-conference presentation) that gives no new information about the business's prospects?"},
    "exec_sudden": {"type": "noul", "instructions": "Does the filing report that a CEO, CFO, president or other top executive is leaving effective immediately, unexpectedly, 'to pursue other interests', for cause, or without a named permanent successor?"},
    "exec_planned": {"type": "noul", "instructions": "Does the filing report a planned executive retirement or leadership transition announced in advance, with a named successor?"},
    "ceo_external": {"type": "noul", "instructions": "Does the filing report the appointment of a new CEO or CFO who is hired from outside the company?"},
    "big_counterparty": {"type": "noul", "instructions": "Is the counterparty in the agreement or transaction described a large, well-known company or a government entity (not a bank, lender, trustee or underwriter)?"},
    "guidance": {"type": "choice", "instructions": "What does the filing say about the company's financial guidance or outlook?",
                 "criteria": {"raised": None, "reaffirmed": None, "lowered": None, "withdrawn": None, "not_mentioned": None}},
    "bad_mandatory": {"type": "noul", "instructions": "Does the filing disclose a restatement or non-reliance on prior financial statements, a material weakness, an auditor resignation or dismissal, a delisting or listing-deficiency notice, a going-concern doubt, or a government investigation or subpoena?"},
    "buyback": {"type": "noul", "instructions": "Does the filing announce a new or increased share repurchase authorization or an accelerated share repurchase?"},
    "dilution": {"type": "noul", "instructions": "Does the filing announce a sale by the company of new common stock or of securities convertible into common stock?"},
    "target": {"type": "noul", "instructions": "Does the filing announce that the company itself has agreed to be acquired, taken private or merged into another company?"},
    "demand": {"type": "noul", "instructions": "Does the filing describe new customer orders, a contract award, a new major customer, or demand stronger than before?"},
    "cuts": {"type": "noul", "instructions": "Does the filing announce layoffs, facility closures, restructuring charges or asset impairments?"},
    "activism": {"type": "noul", "instructions": "Does the filing mention an activist investor, a cooperation or settlement agreement with shareholders, or a proxy contest?"},
    "strategic_review": {"type": "noul", "instructions": "Does the filing announce a review of strategic alternatives or a plan to separate or spin off a business?"},
}

# Leakage probe (forbidden, outcome question) - used only on ~200 DEV documents to test memorisation.
Q_LEAK = {
    "outperf": {"type": "noul", "instructions": "Did this company's stock outperform the overall stock market over the 3 months after this filing?"},
}
