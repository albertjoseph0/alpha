"""Jev (descriptive only): market type + subjective-resolution wording for Polymarket candidate markets.

usage: j01_poly_classify.py DEV|TEST
Candidates = markets with a snapshot whose leading-side price is in [0.80, 0.99] at any horizon.
State = the market question text only (facts in the text; nothing about the future is asked).
The labels are used ONLY for per-type breakdowns / artifact hunting, never to select bets, so no model is
trained on them (hence no LM-dictionary baseline is needed).
Output: data/round5/m07_prediction_markets/poly_jev_<PER>.csv.gz
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from http_cache import ROOT  # noqa
from jev import ask, spent  # noqa

D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
Q = {"mtype": {"type": "choice", "instructions": "What kind of prediction-market question is this?",
               "criteria": {"sports": None, "elections_politics": None, "crypto_price": None, "finance_economics": None,
                            "entertainment_culture": None, "weather_science": None, "geopolitics_war": None, "other": None}},
     "subjective": {"type": "noul", "instructions": "Does resolving this question require subjective judgement or "
                    "interpretation of ambiguous wording (rather than reading a single official number or result)?"}}
snap = pd.read_csv(os.path.join(D, f"snap_poly_{per}.csv.gz"), low_memory=False)
ids = set(snap[snap.p.between(0.80, 0.99)].mkt.astype(str))
s = pd.read_csv(os.path.join(D, f"poly_sample_{per}.csv.gz"), low_memory=False)
s = s[s.id.astype(str).isin(ids)]
rows = []
for i, r in enumerate(s.itertuples()):
    a = ask(state="Market question: " + str(r.question), questions=Q, agent="m07")
    rows.append(dict(mkt=str(r.id), mtype=a["mtype"]["choice"], subjective=a["subjective"]["noul"]))
    if i % 500 == 0:
        print(i, len(s), spent("m07"), flush=True)
pd.DataFrame(rows).to_csv(os.path.join(D, f"poly_jev_{per}.csv.gz"), index=False)
print("done", len(rows), spent("m07"))
