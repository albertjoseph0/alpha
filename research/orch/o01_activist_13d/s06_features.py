"""Feature sets on identical events (investable, priced):
  A  no text   : cover-page stake %, liquidity, price, pre-filing returns/vol, filer 13D history, group size, SPAC flag
  B  A + keyword rules on Item 4 and on the filer names (no LLM)
  C  B + Jev answers (s04_jev.py)
Also picks the representative filing per event (largest percent of class; ties -> longest Item 4), which is
the document Jev reads.

Output: data/orch/o01_activist_13d/panel.parquet
"""
import gzip
import json
import re

import numpy as np
import pandas as pd

from common import D

KW = {
    "kw_board": r"nominat|board seat|board representation|proxy contest|solicit(?:ation of)? proxies|slate of|elect(?:ion of)? (?:its|their|our) (?:own )?(?:nominees|directors)",
    "kw_sale": r"strategic alternatives|sale of the (?:company|issuer)|sell the (?:company|issuer)|explore a sale|maximi[sz]e (?:shareholder|stockholder) value",
    "kw_capital": r"repurchase|buyback|buy back|special dividend|return(?:ing)? (?:of )?capital|capital allocation|balance sheet",
    "kw_oper": r"cost reduction|cost cutting|operating performance|operational|margins|executive compensation|corporate governance|management team",
    "kw_undervalued": r"undervalued|does not reflect|intrinsic value|significant discount|attractive investment opportunity",
    "kw_letter": r"\bletter\b",
    "kw_agreement": r"cooperation agreement|standstill|settlement agreement|nomination agreement",
    "kw_tender": r"tender offer|going private|take the (?:company|issuer) private|proposal to acquire|non-binding (?:proposal|indication)|indication of interest|acquire all",
    "kw_deal": r"merger agreement|exchange agreement|business combination|securities purchase agreement|subscription agreement|in connection with the (?:merger|closing|offering|ipo|initial public offering)|pursuant to the (?:merger|plan)|founder|compensation|grant(?:ed)? of|restricted stock|bankruptcy|plan of reorganization",
    "kw_invest_only": r"for investment purposes|investment purposes only",
    "kw_noplans": r"(?:no|not have any) (?:present |current )?plans? or proposals?",
    "kw_engage": r"engage in (?:discussions|a dialogue|communications)|communicate with|conversations with|dialogue with|discussions with (?:management|the board)",
    "kw_hostile": r"litigation|lawsuit|books and records|special meeting|withhold|consent solicitation|replace (?:the|a majority of the) board",
}
FN = {
    "fn_fund": r"\b(?:capital|partners|fund|management|advisors|advisers|investments?|master|opportunit\w*|value|asset)\b",
    "fn_corp": r"\b(?:inc|corp|corporation|ltd|limited|plc|holdings?|group|co)\b",
    "fn_lp": r"\b(?:l\.?p\.?|llc|l\.l\.c\.)\b",
}
A_COLS = ["pct", "pct_missing", "log_adv", "log_px", "ret_m20", "ret_m126", "vol60", "ret_fd", "log_n_init",
          "log_n_all", "n_acc", "n_filers", "spac"]
B_COLS = A_COLS + list(KW) + list(FN) + ["fn_person", "log_len"]


def main():
    ev = pd.read_parquet(D / "events.parquet")
    ev = ev[ev["investable"] & ev["entry_date"].notna()].copy()
    with gzip.open(D / "texts.jsonl.gz", "rt") as fh:
        tx = pd.DataFrame([json.loads(l) for l in fh]).drop_duplicates("adsh").set_index("adsh")
    rep, i4, pct = [], [], []
    for lst in ev["adsh_list"]:
        cand = [a for a in lst.split("|") if a in tx.index]
        if not cand:
            rep.append(None); i4.append(""); pct.append(np.nan); continue
        t = tx.loc[cand]
        t = t.assign(_p=t["pct"].fillna(-1).astype(float), _n=t["n_chars"]).sort_values(["_p", "_n"], ascending=False)
        rep.append(t.index[0]); i4.append(t["item4"].iloc[0]); pct.append(t["pct"].max())
    ev["rep_adsh"], ev["item4"] = rep, i4
    ev["pct"] = pd.to_numeric(pd.Series(pct, index=ev.index), errors="coerce")
    ev.loc[(ev["pct"] > 100) | (ev["pct"] <= 0), "pct"] = np.nan
    ev["pct_missing"] = ev["pct"].isna().astype(int)
    ev["pct"] = ev["pct"].fillna(ev["pct"].median()).clip(0, 100)
    ev["log_adv"] = np.log(ev["adv20"])
    ev["log_px"] = np.log(ev["raw_px"])
    ev["log_n_init"] = np.log1p(ev["n_init_365"])
    ev["log_n_all"] = np.log1p(ev["n_all_365"])
    ev["n_filers"] = ev["filer_ciks"].fillna("").str.split("|").str.len()
    ev["spac"] = (ev["sic0"] == "6770").astype(int)
    low = ev["item4"].str.lower()
    for k, pat in KW.items():
        ev[k] = low.str.contains(pat, regex=True).astype(int)
    fn = ev["filer_names"].fillna("").str.lower()
    for k, pat in FN.items():
        ev[k] = fn.str.contains(pat, regex=True).astype(int)
    ev["fn_person"] = ((ev["fn_fund"] + ev["fn_corp"] + ev["fn_lp"]) == 0).astype(int)
    ev["log_len"] = np.log1p(ev["item4"].str.len())
    for c in ["ret_m20", "ret_m126", "ret_fd"]:
        ev[c] = ev[c].clip(-0.9, 3)
    ev.to_parquet(D / "panel.parquet")
    print("events", len(ev), "with text", (ev["item4"].str.len() >= 80).sum())
    print(ev[list(KW) + list(FN) + ["fn_person"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
