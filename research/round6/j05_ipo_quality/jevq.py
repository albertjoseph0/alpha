"""Jev question set and state builder for IPO prospectuses (factual questions only).
QSETS logs every question set tried (DEV only)."""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "round5" / "m06_filing_reader"))
from textprep import name_patterns, anonymise  # read-only reuse of m06's anonymiser

LIMITS = {"cover": 2500, "summary": 7000, "uop": 3500, "risk": 6000, "pss": 4500, "sfd": 3000}
TITLES = {"cover": "COVER PAGE", "summary": "PROSPECTUS SUMMARY (excerpt)", "uop": "USE OF PROCEEDS",
          "risk": "RISK FACTORS (first pages)", "pss": "PRINCIPAL AND SELLING STOCKHOLDERS (excerpt)",
          "sfd": "SUMMARY FINANCIAL DATA (excerpt, table flattened with | separators)"}
BANK = re.compile(r"Goldman,? Sachs(?: & Co\.?(?: LLC)?)?|Morgan Stanley|J\.\s?P\.\s?Morgan|BofA Merrill Lynch|BofA Securities|"
                  r"Merrill Lynch|Citigroup|Citi\b|Credit Suisse|Barclays(?: Capital)?|Deutsche Bank(?: Securities)?|UBS(?: Investment Bank)?|"
                  r"Jefferies|Wells Fargo Securities|RBC Capital Markets|Cowen|Piper (?:Jaffray|Sandler)|Stifel|Raymond James|"
                  r"William Blair|Baird|KeyBanc|Oppenheimer|Leerink|SVB|Evercore|Guggenheim|Needham|Canaccord|Roth|Maxim|"
                  r"Aegis|ThinkEquity|EF Hutton|Boustead|Univest|Network 1|Benchmark|Craig-Hallum|B\. Riley|Ladenburg|"
                  r"Nomura|Macquarie|BMO|TD Securities|Truist|SunTrust|Mizuho|HSBC|CICC|China Renaissance|Huatai|"
                  r"Keefe,? Bruyette|Sandler O.Neill|Stephens|Houlihan|Moelis|Lazard|Tudor,? Pickering|Simmons|Wedbush")


def build_state(sec: dict, company: str, ticker) -> str:
    """Anonymised state. Underwriter names are replaced by tier tags so Jev sees tier, not identity."""
    pats = name_patterns(company, None, ticker if isinstance(ticker, str) else None)
    parts = []
    for k, lim in LIMITS.items():
        t = (sec.get(k) or "")[:lim]
        t = re.sub(r"(?:\s*\|\s*){2,}", " | ", t)
        t = anonymise(t, pats)
        parts.append(f"=== {TITLES[k]} ===\n{t.strip()}")
    return "\n\n".join(parts)


YN = lambda s: {"type": "noul", "instructions": s}

Q_V1 = {
    "profitable": YN("According to the summary financial data or text, did the company report positive net income "
                     "(a net profit, not a net loss) for its most recent full fiscal year?"),
    "revenue": YN("Does the company report meaningful product or service revenue (not only grants, interest or "
                  "collaboration income), i.e. is it past the pre-revenue stage?"),
    "uop": {"type": "choice", "instructions": "What is the main stated use of the net proceeds the company receives from "
            "this offering? (If the company receives no proceeds because only selling stockholders sell, answer "
            "pay_existing_holders.)",
            "criteria": {"growth_capex_rnd": "expanding operations, capital expenditures, research and development, clinical trials",
                         "general_corporate": "general corporate purposes and working capital without a specific main use",
                         "repay_debt": "repaying or redeeming indebtedness",
                         "pay_existing_holders": "payments, distributions, dividends or share/unit purchases benefiting existing owners, sponsors or selling stockholders",
                         "acquisitions": "funding acquisitions"}},
    "sponsor": {"type": "choice", "instructions": "Before the offering, who is the main owner or backer of the company "
                "according to the principal stockholders section and summary?",
                "criteria": {"venture_capital": "venture capital funds", "private_equity": "private equity or buyout sponsor",
                             "parent_corporation": "a parent company or corporate owner (carve-out or spin-out)",
                             "founders_management": "founders, management or families",
                             "dispersed_other": "dispersed holders, government, or other"}},
    "insider_selling": {"type": "score", "instructions": "How large a share of the shares offered in this offering is "
                        "being sold by existing (selling) stockholders rather than newly issued by the company?",
                        "criteria": ["none: all shares newly issued by the company", "small minority sold by existing holders",
                                     "about half", "majority sold by existing holders", "all shares sold by existing holders"]},
    "dual_class": YN("Will the company have more than one class of common stock with different voting rights after the offering?"),
    "controlled": YN("Does the prospectus state the company will be a 'controlled company' under exchange listing rules?"),
    "material_weakness": YN("Does the prospectus disclose a material weakness in the company's internal control over financial reporting?"),
    "customer_conc": YN("Does the prospectus say that a small number of customers (or one customer) account for a large "
                        "share of revenue?"),
    "lead_uw": {"type": "choice", "instructions": "Which bank is listed first among the underwriters (lead book-running "
                "manager) on the cover page?",
                "criteria": {"bulge_bracket": "Goldman Sachs, Morgan Stanley, J.P. Morgan, BofA/Merrill Lynch, Citigroup, Credit Suisse, Barclays, Deutsche Bank or UBS",
                             "mid_tier": "another established investment bank (e.g. Jefferies, RBC, Wells Fargo, Piper, Cowen, Stifel, Raymond James, William Blair, Leerink, Evercore)",
                             "small_boutique": "a small or boutique broker-dealer"}},
    "spac": YN("Is this company a blank check company or special purpose acquisition company (SPAC) with no operating business?"),
    "biotech_preclinical": YN("Is the company a clinical-stage or pre-clinical biotechnology or drug development company "
                              "without approved products?"),
    "going_concern": YN("Does the text mention substantial doubt about the company's ability to continue as a going concern?"),
    "foreign_ops": YN("Are the company's main operations located outside the United States?"),
}
QSETS = {"v1": Q_V1}

# Forbidden leakage-probe question (asked on ~200 DEV docs with a short state, never used as a feature)
Q_LEAK = {"leak": YN("Did this company's stock outperform the overall U.S. stock market over the 12 months after this "
                     "initial public offering?")}
