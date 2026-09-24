"""Jev question sets. Every set tried is logged here (brief: keep small). Factual comparison questions only.

V1: first and (planned) only DEV set. Frozen in PREREG.md before TEST.
"""

SEV5 = ["much less", "somewhat less", "about the same", "somewhat more", "much more"]

V1 = {
    "rf_added": {"type": "score", "criteria": ["none", "minor", "material"],
                 "instructions": "In risk_factors, how substantive are the risks described in added_in_current that are "
                                 "genuinely new (not just rewording of a risk in removed_from_prior)?"},
    "rf_removed": {"type": "score", "criteria": ["none", "minor", "material"],
                   "instructions": "In risk_factors, how substantive are the risks in removed_from_prior that no longer "
                                   "appear in any form in added_in_current?"},
    "rf_severity": {"type": "score", "criteria": SEV5,
                    "instructions": "Taking all changes to risk_factors together, does the current version describe the "
                                    "company's risks as less or more severe than the prior version?"},
    "cosmetic": {"type": "score", "criteria": ["all cosmetic", "mostly cosmetic", "mixed", "mostly substantive", "all substantive"],
                 "instructions": "Across all sections, are the differences between the versions cosmetic (rewording, "
                                 "reordering, updated figures or dates) or substantive (new facts, events or risks)?"},
    "litigation_new": {"type": "noul",
                       "instructions": "Does added_in_current (any section) mention a lawsuit, government or regulatory "
                                       "investigation, subpoena, enforcement action or settlement that is not mentioned "
                                       "in removed_from_prior?"},
    "liquidity_stress": {"type": "noul",
                         "instructions": "Does added_in_current contain going-concern doubt, covenant breach or waiver, "
                                         "credit rating downgrade, or liquidity strain language?"},
    "customer_conc": {"type": "choice",
                      "criteria": {"increased": None, "no_change_or_not_mentioned": None, "decreased": None},
                      "instructions": "Did the text's description of dependence on a few large customers or "
                                      "customer concentration increase, decrease, or not change?"},
    "outlook_tone": {"type": "score", "criteria": ["much more negative", "more negative", "unchanged", "more positive", "much more positive"],
                     "instructions": "Comparing the added and removed text of management_discussion, is the current "
                                     "description of business conditions, demand and outlook more negative or more positive?"},
    "accounting_segment": {"type": "noul",
                           "instructions": "Does added_in_current newly disclose an accounting policy change, restatement, "
                                           "material weakness, goodwill or asset impairment, or a change in reportable segments?"},
    "incident_new": {"type": "noul",
                     "instructions": "Does added_in_current newly disclose an actual supply-chain disruption, tariff or "
                                     "trade-restriction impact, cybersecurity incident, or product recall?"},
    "restructuring": {"type": "noul",
                      "instructions": "Does added_in_current newly mention restructuring, layoffs, plant or store "
                                      "closures, or a cost-reduction program?"},
    "mna": {"type": "noul",
            "instructions": "Does added_in_current newly describe a pending or completed acquisition, merger, "
                            "divestiture or spin-off?"},
}

# Leakage probe (forbidden question, never used as a feature)
PROBE = {
    "outperform_12m": {"type": "noul",
                       "instructions": "Did this company's stock outperform the overall US stock market over the 12 "
                                       "months after this report was filed?"},
}

LOG = [
    ("V1", "12 questions above; first set, used for DEV and (if kept) TEST"),
]
