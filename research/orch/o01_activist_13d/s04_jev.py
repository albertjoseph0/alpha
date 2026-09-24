"""Score each 13D's Item 4 with Jev (factual questions only; names/dates stripped), plus a separate
filer-type question that sees ONLY the filer names (no subject company), and a leakage probe.

Output: data/orch/o01_activist_13d/jev.parquet (one row per adsh, numeric feature columns)
        data/orch/o01_activist_13d/probe.parquet (forbidden-question answers on a DEV sample)
"""
import gzip
import json
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
from jev import ask, spent  # noqa: E402

D = ROOT / "data" / "orch" / "o01_activist_13d"
AGENT = "o01"

INTENT = {
    "passive": "Holds the shares for investment only; no specific plans beyond standard boilerplate language",
    "engagement": "Intends to talk with management or the board about strategy, without specific demands",
    "board": "Seeks board seats, nominates directors, or threatens or runs a proxy contest",
    "sale": "Pushes for a sale of the company, a merger, or a review of strategic alternatives",
    "capital_return": "Pushes for buybacks, dividends, or balance-sheet changes",
    "operational": "Pushes for operational changes, cost cuts, or management changes",
    "buyout": "The reporting person itself proposes to acquire or take private the company, or makes a tender offer",
    "insider_or_deal": "Shares were received through a merger, financing, compensation, restructuring, or founder or insider holdings",
}
QUESTIONS = {
    "intent": {"type": "choice", "instructions": "What is the main purpose the reporting person states for acquiring the shares?",
               "criteria": INTENT},
    "hostility": {"type": "score", "instructions": "How confrontational is the reporting person toward the company's board or management?",
                  "criteria": ["supportive or cooperative", "neutral", "critical", "hostile (proxy fight, litigation, or public attack)"]},
    "letter_sent": {"type": "noul", "instructions": "Has the reporting person already sent a letter, proposal, or demand to the company's board or management?"},
    "undervalued": {"type": "noul", "instructions": "Does the text say the shares are undervalued, or that the market price does not reflect the company's value?"},
    "agreement": {"type": "noul", "instructions": "Does the text describe a cooperation, standstill, settlement, or nomination agreement with the company?"},
    "specific_demand": {"type": "noul", "instructions": "Does the reporting person state at least one specific demand or proposal (not just a general reservation of rights)?"},
}
FILER_Q = {"filer_type": {"type": "choice", "instructions": "What kind of entity or person is the reporting person?",
                          "criteria": {"hedge_fund": "Hedge fund, activist fund, or investment adviser",
                                       "private_equity": "Private equity, venture capital, or holding company investor",
                                       "operating_company": "An operating company (corporate strategic investor)",
                                       "individual": "An individual person or family trust",
                                       "financial_institution": "Bank, insurance company, or pension fund",
                                       "other": None}}}
PROBE_Q = {"probe_outperform": {"type": "noul", "instructions": "Did the company's stock outperform the overall stock market over the 12 months after this filing?"}}

DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(19|20)\d{2}\b")


def anonymize(text: str, subject: str, filers: str) -> str:
    t = DATE.sub("[date]", text)
    for name in [subject] + [re.sub(r"\s+\(CIK.*", "", x) for x in str(filers).split(" | ")]:
        name = re.sub(r"\s+\(.*", "", str(name)).strip()
        for token in {name, name.replace(",", ""), " ".join(name.split()[:2])}:
            if len(token) >= 4:
                t = re.sub(re.escape(token), "[entity]", t, flags=re.I)
    return t[:9000]


def flatten(adsh, a):
    row = {"adsh": adsh}
    for k, v in a.items():
        if v["type"] == "noul":
            row[k] = v["noul"]
        elif v["type"] == "score":
            row[k] = v["score"]
        elif v["type"] == "choice":
            row[k] = v["choice"]
            for opt, p in v["probabilities"].items():
                row[f"{k}_p_{opt}"] = p
            row[f"{k}_conf"] = v.get("confidence")
    return row


def main(probe_n: int = 300):
    f = pd.read_csv(D / "filings.csv", dtype=str).set_index("adsh")
    with gzip.open(D / "texts.jsonl.gz", "rt") as fh:
        tx = pd.DataFrame([json.loads(l) for l in fh]).drop_duplicates("adsh").set_index("adsh")
    tx = tx[tx["n_chars"] >= 80]
    jobs = []
    for adsh, r in tx.iterrows():
        m = f.loc[adsh]
        jobs.append((adsh, anonymize(r["item4"], m["subject_name"], m["filer_names"]), str(m["filer_names"])[:600]))
    print("scoring", len(jobs), "spent so far", spent(AGENT), flush=True)

    def one(job):
        adsh, state, filers = job
        try:
            a = ask(state, QUESTIONS, agent=AGENT)
            b = ask({"reporting_person_names": filers}, FILER_Q, agent=AGENT)
            return flatten(adsh, {**a, **b})
        except Exception as e:  # noqa: BLE001
            return {"adsh": adsh, "error": str(e)[:200]}

    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, jobs))
    pd.DataFrame(rows).to_parquet(D / "jev.parquet")
    print("done", spent(AGENT), flush=True)

    # leakage probe on a DEV sample (filings 2014-2019)
    dev = [j for j in jobs if "2014" <= f.loc[j[0], "file_date"][:4] <= "2019"]
    import random
    random.Random(0).shuffle(dev)
    prow = []
    for adsh, state, _ in dev[:probe_n]:
        try:
            prow.append({"adsh": adsh, "probe": ask(state, PROBE_Q, agent=AGENT)["probe_outperform"]["noul"]})
        except Exception as e:  # noqa: BLE001
            prow.append({"adsh": adsh, "probe": None, "error": str(e)[:200]})
    pd.DataFrame(prow).to_parquet(D / "probe.parquet")
    print("probe done", spent(AGENT), flush=True)


if __name__ == "__main__":
    main()
