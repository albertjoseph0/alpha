"""Jev features for every statement (diffed against the previous statement) and every minutes document.

Question set v1 (frozen before any backtest; logged in README). Factual questions about what the text says only.
State = anonymised text (no dates, years, chair or member names, vote rolls). One call per document.
Output: data/round6/j03_fomc/jev_scores.parquet
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
from jev import ask, spent  # noqa: E402

D = ROOT / "data" / "round6" / "j03_fomc"
AGENT = "j03"
QSET = "v1"

Q_STMT = {
    "hawk_shift": {"type": "score", "instructions": "Compared with the PREVIOUS STATEMENT, how does the monetary policy stance and "
                   "policy bias expressed in the CURRENT STATEMENT shift?",
                   "criteria": ["much more dovish (toward easing)", "somewhat more dovish", "essentially unchanged",
                                "somewhat more hawkish", "much more hawkish (toward tightening)"]},
    "guidance": {"type": "choice", "instructions": "Compared with the PREVIOUS STATEMENT, what does the CURRENT STATEMENT's language "
                 "about the future path of the policy rate (forward guidance, balance of risks, policy bias) signal?",
                 "criteria": {"more_tightening_signalled": None, "no_change_in_signal": None, "more_easing_signalled": None}},
    "balance_sheet": {"type": "choice", "instructions": "What does the CURRENT STATEMENT say about the central bank's balance sheet or "
                      "asset purchases, relative to the PREVIOUS STATEMENT?",
                      "criteria": {"expansion_or_more_purchases": None, "no_change_or_not_mentioned": None,
                                   "reduction_or_fewer_purchases": None}},
    "infl_vs_growth": {"type": "score", "instructions": "In the CURRENT STATEMENT, which concern is emphasized more: weakness in "
                       "economic growth and employment, or inflation that is too high?",
                       "criteria": ["almost entirely growth/employment weakness", "mostly growth/employment weakness", "balanced",
                                    "mostly inflation", "almost entirely inflation"]},
    "new_risk": {"type": "noul", "instructions": "Does the CURRENT STATEMENT mention a risk, concern or development that is not "
                 "mentioned in the PREVIOUS STATEMENT?"},
    "action": {"type": "choice", "instructions": "What policy-rate action does the CURRENT STATEMENT announce?",
               "criteria": {"raised": None, "lowered": None, "unchanged": None, "not_stated": None}},
}

Q_MIN = {
    "hawk": {"type": "score", "instructions": "Overall, how hawkish or dovish is the Committee's policy discussion in these minutes?",
             "criteria": ["very dovish (leaning toward easing)", "dovish", "neutral", "hawkish", "very hawkish (leaning toward tightening)"]},
    "future_policy": {"type": "choice", "instructions": "What do the minutes say participants saw as the likely direction of future "
                      "policy-rate changes?",
                      "criteria": {"further_tightening_likely": None, "on_hold_or_unclear": None, "further_easing_likely": None}},
    "balance_sheet": {"type": "choice", "instructions": "What do the minutes say about the central bank's balance sheet or asset purchases?",
                      "criteria": {"expansion_or_more_purchases": None, "no_change_or_not_discussed": None,
                                   "reduction_or_fewer_purchases": None}},
    "infl_vs_growth": {"type": "score", "instructions": "In these minutes, which concern is emphasized more: weakness in economic growth "
                       "and employment, or inflation that is too high?",
                       "criteria": ["almost entirely growth/employment weakness", "mostly growth/employment weakness", "balanced",
                                    "mostly inflation", "almost entirely inflation"]},
    "new_risk": {"type": "noul", "instructions": "Do the minutes highlight a new or increased downside risk to economic growth or "
                 "financial stability?"},
}


def stmt_state(cur, prev):
    return ("PREVIOUS STATEMENT:\n" + (prev if isinstance(prev, str) else "(none)") + "\n\nCURRENT STATEMENT:\n" + cur)


def pdiff(a, key, up, down):
    p = a[key]["probabilities"]
    return p.get(up, 0) - p.get(down, 0)


def main(limit=None):
    d = pd.read_parquet(D / "docs.parquet")
    out = []
    for k, r in d.iterrows():
        if limit and k >= limit:
            break
        if r.kind == "S":
            a = ask(stmt_state(r.text, r.prev_text), Q_STMT, agent=AGENT)
            row = dict(J_hawk=a["hawk_shift"]["score"] - 2, J_guid=pdiff(a, "guidance", "more_tightening_signalled", "more_easing_signalled"),
                       J_bs=pdiff(a, "balance_sheet", "reduction_or_fewer_purchases", "expansion_or_more_purchases"),
                       J_infl=a["infl_vs_growth"]["score"] - 2, J_risk=a["new_risk"]["noul"],
                       J_action=a["action"]["choice"], J_hawk_level=np.nan,
                       conf_min=min(v.get("confidence", 1.0) for v in a.values() if isinstance(v, dict) and "confidence" in v))
        else:
            a = ask(r.text, Q_MIN, agent=AGENT)
            row = dict(J_hawk_level=a["hawk"]["score"] - 2, J_guid=pdiff(a, "future_policy", "further_tightening_likely", "further_easing_likely"),
                       J_bs=pdiff(a, "balance_sheet", "reduction_or_fewer_purchases", "expansion_or_more_purchases"),
                       J_infl=a["infl_vs_growth"]["score"] - 2, J_risk=a["new_risk"]["noul"], J_action=None,
                       conf_min=min(v.get("confidence", 1.0) for v in a.values() if isinstance(v, dict) and "confidence" in v))
        row.update(kind=r.kind, release=r.release, raw=json.dumps(a))
        out.append(row)
        if k % 25 == 0:
            print(k, r.kind, r.release.date(), {x: (round(v, 2) if isinstance(v, float) else v) for x, v in row.items() if x.startswith("J_")},
                  spent(AGENT), flush=True)
    j = pd.DataFrame(out)
    # minutes: hawk shift = change of hawk level vs previous minutes (computed in code)
    mm = j.kind == "M"
    j.loc[mm, "J_hawk"] = j.loc[mm, "J_hawk_level"].diff()
    j.to_parquet(D / "jev_scores.parquet")
    print(j.groupby("kind")[["J_hawk", "J_guid", "J_bs", "J_infl", "J_risk", "conf_min"]].describe().T.round(3))
    print("spent", spent(AGENT))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
