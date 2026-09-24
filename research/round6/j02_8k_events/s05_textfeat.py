"""Feature set (b): Loughran-McDonald dictionary tone (pysentiment2 LM) and keyword rules on the 8-K body and
EX-99 text; plus document-structure fields used by feature set (a). -> DATA/textfeat.parquet"""
import re
import numpy as np, pandas as pd
import pysentiment2 as ps
from common import DATA, read_texts
from state import clean_body

lm = ps.LM()
KW = {
    "buyback": r"repurchase|buyback|buy back",
    "div_up": r"increase[sd]? (?:in )?(?:the |its )?(?:quarterly )?dividend|dividend increase|special (?:cash )?dividend",
    "debt": r"senior notes|notes due|indenture|credit agreement|term loan|revolving credit|commercial paper",
    "equity": r"offering of (?:\S+ )?(?:shares|common stock)|at[- ]the[- ]market|equity distribution|convertible",
    "acquire": r"\bacquir(?:e|es|ed|ing)\b|acquisition of",
    "target": r"agreement and plan of merger|merger sub|surviving corporation|will be acquired|to be acquired|take[- ]private",
    "divest": r"divest|spin[- ]?off|separation of|sale of (?:its|the|our)",
    "ceo": r"chief executive officer",
    "cfo": r"chief financial officer",
    "immediate": r"effective immediately|with immediate effect",
    "other_int": r"pursue other|other (?:interests|opportunities)|personal reasons",
    "retire": r"\bretire",
    "successor": r"successor|succeed",
    "interim": r"\binterim\b",
    "terminat": r"terminat",
    "contract": r"\bcontract\b|\baward(?:ed)?\b|supply agreement|collaboration|partnership",
    "g_raise": r"rais(?:e|es|ed|ing) (?:\S+ ){0,6}(?:guidance|outlook)|(?:guidance|outlook) (?:\S+ ){0,4}raised",
    "g_lower": r"(?:lower|reduc|cut)\w* (?:\S+ ){0,6}(?:guidance|outlook)|withdr\w+ (?:\S+ ){0,6}(?:guidance|outlook)",
    "g_reaff": r"reaffirm|reiterat",
    "layoff": r"layoff|workforce reduction|reduction in (?:force|workforce)|restructuring",
    "impair": r"impairment|write[- ]?(?:down|off)",
    "investig": r"subpoena|investigation|wells notice|material weakness|non-reliance|restate",
    "litig": r"lawsuit|litigation|settlement|verdict|class action",
    "approval": r"\bfda\b|approv(?:al|ed)",
    "activist": r"cooperation agreement|activist|nominat\w+ agreement|proxy contest",
    "strategic": r"strategic alternatives|strategic review",
    "cyber": r"cybersecurity incident|unauthorized access|ransomware",
    "delist": r"delist|listing standard|continued listing",
    "auditor": r"independent registered public accounting firm.{0,80}(?:dismiss|resign|engag)",
}
KWC = {k: re.compile(v, re.I) for k, v in KW.items()}
rows = []
for r in read_texts():
    body = clean_body(r["body"], 25000)
    txt = body + "\n" + (r["ex"] or "")
    toks = lm.tokenize(txt)
    s = lm.get_score(toks)
    d = {"acc": r["acc"], "n_words": len(toks), "lm_pos": s["Positive"] / max(len(toks), 1),
         "lm_neg": s["Negative"] / max(len(toks), 1), "lm_pol": s["Polarity"],
         "has_ex99": int(bool(r["ex"])), "has_ex10": int(any(re.match(r"EX-10\.\d", x) for x in r["other_ex"])),
         "has_ex2": int(any(x.startswith("EX-2.") for x in r["other_ex"]))}
    for k, c in KWC.items():
        d["kw_" + k] = int(bool(c.search(txt)))
    rows.append(d)
F = pd.DataFrame(rows)
F.to_parquet(DATA / "textfeat.parquet")
print(len(F)); print(F.drop(columns="acc").mean().round(3).to_string())
