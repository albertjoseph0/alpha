"""Step 4: text features on identical events.
(b) keyword rules (no LLM) on the same anonymised section windows, plus SIC 2-digit mismatch spin vs parent.
(c) Jev answers to the frozen question set (questions.py), one call per document.
Usage: 04_features.py [kw|jev|probe] [dev|test|all]
Writes data/round6/j04_spinoffs/features_kw.csv, features_jev.csv, probe.csv (append-safe, cached)."""
import json, os, re, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/user/alpha/research/round5")
from jev import ask, spent  # noqa: E402
from questions import QUESTIONS, PROBE, state_from_sections, QSET_VERSION  # noqa: E402

D = "/home/user/alpha/data/round6/j04_spinoffs"
AGENT = "j04"
mode = sys.argv[1] if len(sys.argv) > 1 else "kw"
period = sys.argv[2] if len(sys.argv) > 2 else "dev"

ev = pd.read_csv(f"{D}/events.csv", parse_dates=["first_trade"])
ev = ev[ev.yf_ticker.notna() | ev.completed.fillna(False)]  # priced events, plus completed-but-unpriced (for survivorship)
ev["period_date"] = ev.first_trade.fillna(pd.to_datetime(ev.doc_date) + pd.Timedelta(days=21))
if period == "dev":
    ev = ev[(ev.period_date >= "2004-01-01") & (ev.period_date < "2015-01-01")]
elif period == "test":
    ev = ev[ev.period_date >= "2015-01-01"]
ev = ev[ev.cik.apply(lambda c: os.path.exists(f"{D}/sections/{c}.json"))]
print(mode, period, len(ev), "events")

GRANT = re.compile(r"founders?'? (?:grant|award)|(?:special|one-time|launch|ipo|spin-?off|separation|transaction|retention|"
                   r"sign-on|inducement|make-whole|initial) (?:equity |stock |rsu |option |restricted stock |performance )?(?:grant|award)", re.I)
DEBT_WORDS = re.compile(r"proceeds|borrow|notes|term loan|credit facility|indebtedness|debt financing", re.I)
TO_PARENT = re.compile(r"(?:cash )?(?:distribution|dividend|payment|transfer)s? [^.]{0,80}to Parent|Parent[^.]{0,40}receive[^.]{0,60}(?:cash|\$)", re.I)
RETAIN = re.compile(r"Parent will (?:retain|continue to own|own approximately)|retain(?:s|ed)? [^.]{0,60}(?:\d+(?:\.\d+)?%|percent) of (?:our|the|SpinCo)", re.I)
NO_RETAIN = re.compile(r"Parent will (?:not|no longer) (?:own|retain|hold)|distribut\w+ all of (?:the )?(?:outstanding |issued )?(?:shares|common stock)", re.I)
DIV_YES = re.compile(r"(?:we )?(?:intend|expect|anticipate|plan)s? to pay (?:a )?(?:regular |quarterly |an annual )?(?:cash )?dividends?", re.I)
DIV_NO = re.compile(r"(?:do not|don't) (?:currently )?(?:intend|expect|anticipate|plan) to (?:declare or )?pay", re.I)
REASON_KW = {"activist": r"activist|shareholder (?:proposal|pressure)|investor (?:feedback|input)|stockholder engagement",
             "regulatory": r"regulat\w+ (?:requirement|approval|constraint)|antitrust|consent decree|divest\w* (?:required|order)",
             "tax": r"\bREIT\b|tax[- ](?:efficient|advantaged|benefits? of the)",
             "underperf": r"non-?core|under-?perform|slower[- ]growth|declin\w+ (?:revenue|sales|business)|turnaround|distract",
             "focus": r"focus|strategic (?:flexibility|priorities)|pure[- ]play"}


def sentences(txt):
    return re.split(r"(?<=[.;])\s+", txt)


def kw_row(cik):
    sec = json.load(open(f"{D}/sections/{cik}.json"))
    j = {k: " ".join(v) for k, v in sec.items()}
    fin = [s for s in sentences(j["financing"] + " " + j["stake"]) if TO_PARENT.search(s)]
    r = dict(cik=cik,
             kw_grants=int(bool(GRANT.search(j["equity"]))),
             kw_debt_to_parent=int(any(DEBT_WORDS.search(s) for s in fin)),
             kw_parent_stake=int(bool(RETAIN.search(j["stake"] + " " + j["reasons"])) and not bool(NO_RETAIN.search(j["stake"]))),
             kw_pays_dividend=int(bool(DIV_YES.search(j["dividend"])) and not bool(DIV_NO.search(j["dividend"]))))
    for k, p in REASON_KW.items():
        r[f"kw_reason_{k}"] = len(re.findall(p, j["reasons"], re.I))
    return r


def jev_row(cik, qs):
    sec = json.load(open(f"{D}/sections/{cik}.json"))
    st = state_from_sections(sec)
    a = ask(st, qs, agent=AGENT)
    r = dict(cik=cik, state_chars=len(st))
    for k, v in a.items():
        if v.get("type") == "noul":
            r[f"jev_{k}"] = v["noul"]
        elif v.get("type") == "choice":
            r[f"jev_{k}"] = v["choice"]
            r[f"jev_{k}_conf"] = v.get("confidence")
            for c, p in v["probabilities"].items():
                r[f"jev_{k}_p_{c}"] = p
        elif v.get("type") == "score":
            r[f"jev_{k}"] = v["score"]
            r[f"jev_{k}_conf"] = v.get("confidence")
    return r


if mode == "kw":
    out = pd.DataFrame([kw_row(c) for c in ev.cik])
    fn = f"{D}/features_kw_{period}.csv"
elif mode in ("jev", "probe"):
    qs = QUESTIONS if mode == "jev" else PROBE
    rows = []
    for i, c in enumerate(ev.cik):
        try:
            rows.append(jev_row(c, qs))
        except Exception as e:  # noqa: BLE001
            print("jev fail", c, str(e)[:200], flush=True)
        if i % 20 == 0:
            print(i, spent(AGENT), flush=True)
    out = pd.DataFrame(rows)
    out["qset"] = QSET_VERSION if mode == "jev" else "probe"
    fn = f"{D}/features_{mode}_{period}.csv"
out.to_csv(fn, index=False)
print("wrote", fn, len(out), spent(AGENT))
