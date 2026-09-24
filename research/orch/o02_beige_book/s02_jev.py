"""Jev scores of each Beige Book national summary: direction of change per sector, as the report describes it.

The Beige Book itself reports change "since the previous report", so each edition is scored on its own.
Input is the national summary only (cut before the district sections), with dates and years removed.
Output: data/orch/o02_beige_book/jev_scores.parquet (one row per release; one expected-direction column
per sector in [-2, +2], NaN when Jev says the sector isn't mentioned) and probe.parquet (leakage probe).
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

D = ROOT / "data" / "orch" / "o02_beige_book"
AGENT = "o02"
SECTORS = {
    "overall": "overall economic activity",
    "consumer": "consumer spending and retail sales (including auto sales and tourism)",
    "manufacturing": "manufacturing activity",
    "resi_re": "residential real estate and home construction",
    "cre": "commercial real estate and nonresidential construction",
    "banking": "bank lending, loan demand, and financial services",
    "energy": "energy and natural resources activity (oil, gas, mining)",
    "agriculture": "agriculture",
    "services": "nonfinancial services, including technology, business services, and health care",
    "transport": "transportation and freight",
    "labor": "labor demand and employment",
    "prices": "price pressures and inflation",
}
LEVELS = {"declined_sharply": -2, "declined": -1, "flat": 0, "grew": 1, "grew_strongly": 2}
CUTS = ["Federal Reserve Bank of Boston", "First District", "Highlights by Federal Reserve District",
        "Boston Economic activity", "Boston First District"]
DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b(\s+\d{1,2},?)?(\s+(19|20)\d{2})?|\b(19|20)\d{2}\b")


def national_summary(text: str) -> str:
    cut = len(text)
    for c in CUTS:
        i = text.find(c, 400)
        if 0 < i < cut:
            cut = i
    return DATE.sub("[date]", text[:min(cut, 20000)])


def questions():
    q = {}
    for k, desc in SECTORS.items():
        q[k] = {"type": "choice",
                "instructions": f"According to this report, how did {desc} change since the previous report?",
                "criteria": {"declined_sharply": "Declined substantially or sharply",
                             "declined": "Declined slightly or modestly, or softened",
                             "flat": "Little changed, flat, or mixed",
                             "grew": "Grew slightly or modestly",
                             "grew_strongly": "Grew substantially, strongly, or robustly",
                             "not_mentioned": "The report does not describe this"}}
    q["uncertainty"] = {"type": "noul", "instructions": "Does the report emphasize elevated uncertainty or downside risks to the outlook?"}
    q["outlook"] = {"type": "choice", "instructions": "How does the report describe businesses' outlook for the coming months?",
                    "criteria": {"pessimistic": None, "cautious": None, "neutral_or_not_mentioned": None,
                                 "optimistic": None}}
    return q


def expected(ans):
    p = ans["probabilities"]
    pm = sum(p.get(k, 0) for k in LEVELS)
    if pm < 0.5:
        return float("nan")
    return sum(LEVELS[k] * p.get(k, 0) for k in LEVELS) / pm


def main():
    ed = [json.loads(l) for l in gzip.open(D / "editions.jsonl.gz", "rt")]
    Q = questions()

    def one(e):
        s = national_summary(e["text"])
        a = ask(s, Q, agent=AGENT)
        row = {"release": e["release"], "n_chars": len(s)}
        for k in SECTORS:
            row[k] = expected(a[k])
        row["uncertainty"] = a["uncertainty"]["noul"]
        op = a["outlook"]["probabilities"]
        row["outlook"] = op.get("optimistic", 0) - op.get("pessimistic", 0) - 0.5 * op.get("cautious", 0)
        return row

    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, ed))
    df = pd.DataFrame(rows).sort_values("release")
    df.to_parquet(D / "jev_scores.parquet")
    print(df.describe().round(2).T[["count", "mean", "std"]].to_string())
    probe_q = {"probe": {"type": "noul", "instructions": "Did the US stock market rise over the six months after this report was published?"}}
    pr = []
    for e in ed:
        pr.append({"release": e["release"], "probe": ask(national_summary(e["text"]), probe_q, agent=AGENT)["probe"]["noul"]})
    pd.DataFrame(pr).to_parquet(D / "probe.parquet")
    print("spent", spent(AGENT))


if __name__ == "__main__":
    main()
