"""Cheap text baseline (no LLM): dictionary tone of the sentences about each sector in the national summary.

Same input text as Jev (s02.national_summary: the national summary, dates masked). For each of the 12 sectors,
sentences are selected by keyword regex, and two tones are computed over those sentences:
  * d_<sector>  (PRIMARY baseline, fixed before results): Beige Book direction words,
                (#up - #down) / (#up + #down + #flat), in [-1, 1]; NaN if the sector has no direction words.
  * lm_<sector> (secondary): Loughran-McDonald net tone (#pos - #neg) / (#pos + #neg); NaN if neither.
Output: data/orch/o02_beige_book/dict_scores.parquet (one row per release).
"""
import gzip
import json
import pathlib
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from s02_jev import D, SECTORS, national_summary  # noqa: E402

KEYS = {
    "overall": r"economic activity|\beconomy\b|overall activity|economic growth|economic conditions|business activity",
    "consumer": r"consumer|retail|auto(mobile)? sales|vehicle|tourism|travel|holiday sales|shopping|restaurant",
    "manufacturing": r"manufactur|factor(y|ies)|industrial production",
    "resi_re": r"residential|home sales|housing|homebuild|home construction|single-family|home prices|multifamily",
    "cre": r"commercial real estate|nonresidential|commercial construction|office|leasing|commercial property",
    "banking": r"\bloans?\b|lending|\bcredit\b|\bbank|deposit",
    "energy": r"energy|\boil\b|natural gas|drilling|\brigs?\b|mining|\bcoal\b",
    "agriculture": r"agricultur|\bfarm|\bcrops?\b|livestock|ranch|harvest",
    "services": r"\bservices\b|staffing|software|technology|health care|healthcare|professional",
    "transport": r"transport|freight|trucking|shipping|\brail|cargo|shipments|logistics",
    "labor": r"employment|hiring|\blabor\b|\bjobs?\b|workers|\bwages?\b|headcount|payroll",
    "prices": r"\bprices?\b|inflation|\bcosts?\b",
}
UP = re.compile(r"\b(increas\w*|rose|ris(e|es|ing|en)|gr[eo]w(s|ing|n|th)?|expan\w*|strength\w*|strong\w*|improv\w*|"
                r"gain\w*|accelerat\w*|robust|solid|higher|rebound\w*|recover\w*|brisk|surg\w*|upturn|healthy|"
                r"pick(ed|ing|s)? up|firmed|firming)\b")
DOWN = re.compile(r"\b(decreas\w*|declin\w*|fell|fall(s|ing|en)?|weak\w*|soft(en\w*|er|ness)?|slow\w*|"
                  r"contract(ed|ing|ion)|deteriorat\w*|drop\w*|lower\w*|sluggish|downturn|dampen\w*|subdued|plung\w*|"
                  r"slump\w*|curtail\w*|diminish\w*|eas(ed|ing))\b")
FLAT = re.compile(r"\b(flat|unchanged|steady|stable|little changed|mixed|stabiliz\w*)\b")
SENT = re.compile(r"(?<=[.!?])\s+")
TOK = re.compile(r"[a-z]+")


def lm_sets():
    import pysentiment2
    p = pathlib.Path(pysentiment2.__file__).parent / "static" / "LM.csv"
    d = pd.read_csv(p)
    return set(d.loc[d.Positive > 0, "Word"].str.lower()), set(d.loc[d.Negative > 0, "Word"].str.lower())


def main():
    pos, neg = lm_sets()
    ed = [json.loads(l) for l in gzip.open(D / "editions_fixed.jsonl.gz", "rt")]
    rows = []
    for e in ed:
        sents = [s.lower() for s in SENT.split(national_summary(e["text"]))]
        row = {"release": e["release"]}
        for k in SECTORS:
            sel = [s for s in sents if re.search(KEYS[k], s)]
            txt = " ".join(sel)
            u, dn, f = len(UP.findall(txt)), len(DOWN.findall(txt)), len(FLAT.findall(txt))
            row["d_" + k] = (u - dn) / (u + dn + f) if u + dn + f else np.nan
            toks = TOK.findall(txt)
            p_, n_ = sum(t in pos for t in toks), sum(t in neg for t in toks)
            row["lm_" + k] = (p_ - n_) / (p_ + n_) if p_ + n_ else np.nan
            row["nsent_" + k] = len(sel)
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("release").reset_index(drop=True)
    df.to_parquet(D / "dict_scores.parquet")
    era = np.where(pd.to_datetime(df.release) < "2017-01-01", "pre2017", "2017+")
    cols = ["d_" + k for k in SECTORS]
    print("direction-dictionary tone, mean by era:")
    print(df[cols].groupby(era).mean().round(2).T.to_string())
    print("missing share by era:")
    print(df[cols].isna().groupby(era).mean().round(2).T.to_string())


if __name__ == "__main__":
    main()
