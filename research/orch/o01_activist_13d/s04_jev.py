"""Score each event's representative 13D Item 4 with Jev (factual questions only; subject/filer names, ticker
and dates stripped), plus a separate filer-type question that sees ONLY the filer names, and a leakage probe.

Question set V1 (frozen before any return was looked at; see STATUS.md / PREREG.md).

Usage:  s04_jev.py score [n]      -> jev.parquet (all events in panel.parquet, or the first n for a cost check)
        s04_jev.py probe [n=300]  -> probe.parquet: forbidden question on DEV events, (a) on the same anonymized
                                     state the features use and (b) worst case with name, ticker and date shown
"""
import json
import pathlib
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import D, ROOT

sys.path.insert(0, str(ROOT / "research" / "round5"))
from jev import CACHE, ask, spent  # noqa: E402

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


def anonymize(text: str, subject: str, filers: str, tk: str) -> str:
    t = DATE.sub("[date]", text)
    for name in [subject] + [re.sub(r"\s+\(CIK.*", "", x) for x in str(filers).split(" | ")]:
        name = re.sub(r"\s+\(.*", "", str(name)).strip()
        for token in sorted({name, name.replace(",", ""), " ".join(name.split()[:2])}, key=len, reverse=True):
            if len(token) >= 4:
                t = re.sub(re.escape(token), "[entity]", t, flags=re.I)
    if isinstance(tk, str) and len(tk) >= 2:
        t = re.sub(r"\b" + re.escape(tk.replace("-", ".")) + r"\b", "[ticker]", t)
    return t[:9000]


def state_of(r) -> dict:
    return {"schedule_13d_item4_purpose_of_transaction": anonymize(r["item4"], r["subject_name"], r["filer_names"], r["tk"])}


def filer_state(r) -> dict:
    names = " | ".join(re.sub(r"\s+\(CIK.*", "", x).strip() for x in str(r["filer_names"]).split(" | "))
    return {"reporting_person_names": names[:600]}


def flatten(key, a):
    row = {"key": key}
    for k, v in a.items():
        if "noul" in v:
            row[k] = v["noul"]
        elif "score" in v:
            row[k] = v["score"]
        elif "choice" in v:
            row[k] = v["choice"]
            for opt, p in v.get("probabilities", {}).items():
                row[f"{k}_p_{opt}"] = p
            row[f"{k}_conf"] = v.get("confidence")
    return row


def panel():
    p = pd.read_parquet(D / "panel.parquet")
    return p[p["item4"].str.len() >= 80]


def score(n=None):
    p = panel()
    if n:
        p = p.sample(int(n), random_state=1)
    print("scoring", len(p), "spent so far", spent(AGENT), flush=True)

    def one(item):
        idx, r = item
        try:
            a = ask(state_of(r), QUESTIONS, agent=AGENT)
            b = ask(filer_state(r), FILER_Q, agent=AGENT)
            return flatten(r["rep_adsh"], {**a, **b})
        except Exception as e:  # noqa: BLE001
            return {"key": r["rep_adsh"], "error": str(e)[:200]}

    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, p.iterrows()))
    out = pd.DataFrame(rows).rename(columns={"key": "rep_adsh"})
    out.to_parquet(D / ("jev.parquet" if not n else "jev_sample.parquet"))
    print("done", len(out), "errors", out.get("error", pd.Series(dtype=str)).notna().sum(), "spent", spent(AGENT), flush=True)
    print("cache tokens", cache_tokens(), flush=True)


def probe(n=300):
    p = panel()
    p = p[(p["file_date"] >= "2014-01-01") & (p["file_date"] <= "2019-12-31")]
    idx = list(p.index)
    random.Random(0).shuffle(idx)
    rows = []
    for i in idx[:int(n)]:
        r = p.loc[i]
        named = {"company": r["subject_name"], "ticker": r["tk"], "filing_date": str(r["file_date"].date()),
                 "schedule_13d_item4_purpose_of_transaction": r["item4"][:9000]}
        try:
            a = ask(state_of(r), PROBE_Q, agent=AGENT)["probe_outperform"]["noul"]
            b = ask(named, PROBE_Q, agent=AGENT)["probe_outperform"]["noul"]
            rows.append({"rep_adsh": r["rep_adsh"], "probe_anon": a, "probe_named": b})
        except Exception as e:  # noqa: BLE001
            rows.append({"rep_adsh": r["rep_adsh"], "error": str(e)[:200]})
    pd.DataFrame(rows).to_parquet(D / "probe.parquet")
    print("probe done", len(rows), spent(AGENT), flush=True)


def cache_tokens():
    tot, n = 0, 0
    for f in pathlib.Path(CACHE / AGENT).glob("*/*.json"):
        u = json.loads(f.read_text()).get("usage") or {}
        tot += int(u.get("input_tokens", 0)); n += 1
    return {"calls": n, "input_tokens": tot, "usd": tot * 0.042e-6}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"score": score, "probe": probe}[cmd](*( [arg] if arg else []))
