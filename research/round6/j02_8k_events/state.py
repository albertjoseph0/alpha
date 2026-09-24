"""Build the anonymised Jev state for one 8-K: item list, cleaned body (legal boilerplate removed), and the
narrative of the first EX-99 exhibit. Company names, tickers, URLs and dates are removed (m06 textprep)."""
import re, sys
sys.path.append("/home/user/alpha/research/round5/m06_filing_reader")
from textprep import anonymise, name_patterns, narrative  # noqa: E402  (read-only import)

ITEM_NAMES = {"1.01": "Entry into a Material Definitive Agreement", "1.02": "Termination of a Material Definitive Agreement",
              "1.03": "Bankruptcy or Receivership", "2.01": "Completion of Acquisition or Disposition of Assets",
              "2.03": "Creation of a Direct Financial Obligation", "2.04": "Triggering Events That Accelerate an Obligation",
              "2.05": "Costs Associated with Exit or Disposal Activities", "2.06": "Material Impairments",
              "3.01": "Notice of Delisting or Failure to Satisfy a Listing Rule", "3.02": "Unregistered Sales of Equity Securities",
              "3.03": "Material Modification to Rights of Security Holders", "4.01": "Changes in Registrant's Certifying Accountant",
              "4.02": "Non-Reliance on Previously Issued Financial Statements", "5.01": "Changes in Control of Registrant",
              "5.02": "Departure/Appointment of Directors or Officers; Compensatory Arrangements", "5.03": "Amendments to Articles or Bylaws",
              "5.07": "Submission of Matters to a Vote of Security Holders", "7.01": "Regulation FD Disclosure", "8.01": "Other Events",
              "9.01": "Financial Statements and Exhibits"}
BOIL = re.compile(r"shall not be deemed|does not purport to be complete|incorporated (herein )?by reference|"
                  r"forward-looking statements?|safe harbor|Section 18 of the|Securities Act of 1933|"
                  r"qualified in (its|their) entirety|furnished (herewith|as Exhibit)|Private Securities Litigation", re.I)


RE_SUF = re.compile(r"the Company,? (?:Inc|Incorporated|Corp|Corporation|Co|Company|Ltd|plc|N\.V|LLC|L\.P)\b\.?", re.I)


def clean_body(body, max_chars=3500):
    b = body.replace("|", " ")
    b = re.split(r"Item\s*9\.01", b, flags=re.I)[0]
    sents = re.split(r"(?<=[.;])\s+|\n", b)
    keep = [s.strip() for s in sents if s.strip() and not BOIL.search(s) and len(s.split()) >= 3]
    return re.sub(r"\s+", " ", " ".join(keep))[:max_chars]


def build_state(rec, ev, body_chars=3500, ex_chars=3000):
    pats = name_patterns(ev["company"], ev["name"], ev["ticker"])
    items = [i for i in str(ev["items"]).split(",") if i]
    head = "Form 8-K current report. Items: " + "; ".join(f"{i} {ITEM_NAMES.get(i, '')}".strip() for i in items)
    body = clean_body(rec["body"], body_chars)
    ex = narrative(rec["ex"], ex_chars) if rec.get("ex") else ""
    s = head + "\n\nREPORT:\n" + body
    if ex:
        s += "\n\nPRESS RELEASE (exhibit):\n" + ex
    s = anonymise(s.replace("\u2019", "'").replace("\u2018", "'"), pats)
    return RE_SUF.sub("the Company", s)
