"""Frozen Jev question list (factual, about what the text states). The state holds the CURRENT release
and, when available, the same company's PREVIOUS-quarter release, both anonymised."""

YN = "noul"


def yn(q):
    return {"type": YN, "instructions": q}


def ch(q, opts):
    return {"type": "choice", "instructions": q, "criteria": {o: None for o in opts}}


def sc(q, levels):
    return {"type": "score", "instructions": q, "criteria": levels}


C = "In the CURRENT release, "
QUESTIONS = {
    # guidance
    "guid_dir": ch(C + "what does the company say about its forward financial guidance (full-year or next-quarter "
                   "revenue/earnings outlook) relative to its prior guidance?",
                   ["raised", "maintained_or_reaffirmed", "lowered", "withdrawn_or_suspended", "newly_initiated",
                    "mixed_some_up_some_down", "no_guidance_given"]),
    "guid_spec_vs_prev": ch("Compare the forward guidance in the CURRENT release with the forward guidance in the "
                            "PREVIOUS release. Is the CURRENT guidance",
                            ["more_specific_or_more_items", "about_as_specific", "less_specific_or_fewer_items",
                             "neither_gives_guidance", "no_previous_release_provided"]),
    "outlook_caution": sc(C + "how cautious is the language about the future outlook?",
                          ["very confident", "confident", "neutral", "cautious", "very cautious"]),
    "caution_vs_prev": sc("Compared with the PREVIOUS release, how has the caution of the outlook language in the "
                          "CURRENT release changed? (If no previous release is provided, answer 'about the same'.)",
                          ["much less cautious", "less cautious", "about the same", "more cautious",
                           "much more cautious"]),
    "tone_vs_prev": sc("Compared with the PREVIOUS release, how has the overall tone of the CURRENT release changed? "
                       "(If no previous release is provided, answer 'about the same'.)",
                       ["much more negative", "more negative", "about the same", "more positive",
                        "much more positive"]),
    "ceo_quote_tone": sc(C + "what is the tone of the chief executive's quoted remarks?",
                         ["very negative", "negative", "neutral", "positive", "very positive"]),
    # results
    "rev_dir": ch(C + "how did total revenue (or net sales) for the reported quarter change versus the same "
                  "quarter a year earlier?", ["increased", "roughly_flat", "decreased", "not_stated"]),
    "eps_dir": ch(C + "how did earnings per share for the reported quarter change versus a year earlier?",
                  ["increased", "roughly_flat", "decreased", "turned_to_loss_or_loss_widened", "not_stated"]),
    "beat_own_outlook": yn(C + "does the company state that results were above its own prior guidance, outlook or "
                           "expectations?"),
    "miss_own_outlook": yn(C + "does the company state that results were below its own prior guidance, outlook or "
                           "expectations?"),
    "record": yn(C + "does the company describe any result for the period as a record?"),
    "margin_dir": ch(C + "what does the text say about gross or operating margin for the quarter versus a year earlier?",
                     ["expanded", "stable", "contracted", "not_discussed"]),
    "external_blame": yn(C + "are weak or declining results attributed to external factors such as the economy, "
                         "weather, currency, pandemic, supply chain, tariffs or customer behaviour?"),
    "demand": sc(C + "how is demand, order intake, bookings or backlog described?",
                 ["clearly weakening", "somewhat weakening", "stable or not discussed", "somewhat improving",
                  "clearly strengthening"]),
    "cost_pressure": yn(C + "does the company say that rising costs or inflation hurt its margins or profits?"),
    # unusual items and accounting
    "one_time": yn(C + "is a significant unusual or one-time item (impairment, restructuring charge, litigation "
                   "settlement, gain or loss on a sale, large tax item) reported?"),
    "impairment": yn(C + "is an impairment or write-down of goodwill or other assets reported?"),
    "restructuring": yn(C + "is a restructuring, layoff or cost-reduction programme announced or expanded?"),
    "nongaap_change": yn(C + "does the company say it changed the definition or composition of a non-GAAP or adjusted "
                         "measure, or introduced a new adjusted measure?"),
    "segment_change": yn(C + "is a change in segment or reporting structure announced?"),
    "accounting_issue": yn(C + "is a restatement, material weakness, auditor change, delayed filing or accounting "
                           "investigation mentioned?"),
    "exec_change": yn(C + "is a change of chief executive officer or chief financial officer (departure, retirement "
                      "or appointment) announced?"),
    # capital allocation and balance sheet
    "buyback": ch(C + "what is said about share repurchases?",
                  ["new_or_increased_authorization", "repurchases_continued", "repurchases_paused_or_reduced",
                   "not_mentioned"]),
    "dividend": ch(C + "what is said about the dividend?",
                   ["increased_or_initiated", "maintained", "cut_or_suspended", "not_mentioned"]),
    "mna": yn(C + "does the company announce an acquisition, divestiture, merger, spin-off or strategic review?"),
    "liquidity_stress": yn(C + "does the text mention liquidity concerns, covenant issues, drawing down credit lines, "
                           "or raising capital to shore up the balance sheet?"),
    "disruption": yn(C + "does the company report a significant operational disruption (plant outage, natural "
                     "disaster, cyberattack, strike, recall, pandemic shutdown)?"),
    "capex_cut": yn(C + "does the company announce lower planned capital expenditures or investment?"),
}
assert 20 <= len(QUESTIONS) <= 40
