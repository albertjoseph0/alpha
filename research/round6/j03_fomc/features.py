"""Build the event table: one row per document release (statement or minutes) with
  (a) no-text market-reaction features, (b) dictionary baseline features, and the cleaned/anonymised text.

Event date = the release date (statements: the decision day, released 14:00-14:15 ET, or earlier for
1990s/intermeeting releases; minutes: the published release date, 14:00 ET). A release on a non-trading
day maps to the next trading day. Output: data/round6/j03_fomc/docs.parquet
"""
import collections
import math
import pathlib
import re

import numpy as np
import pandas as pd

import textprep as tp

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "round6" / "j03_fomc"

# Hawkish / dovish phrase dictionary (fixed before any backtest; in the spirit of Apel & Blix Grimaldi 2012
# and the Loughran-McDonald idea of domain word lists). Matched case-insensitively on anonymised text.
HAWK = [r"inflation pressures?", r"heightened inflation", r"higher inflation", r"upside risks? to inflation", r"inflation risks?",
        r"tighten\w*", r"firming", r"firm(?:er)?\b", r"raise\w*", r"increase the target", r"increases? in the target",
        r"remov\w+ (?:of )?(?:policy )?accommodation", r"less accommodative", r"overheat\w*", r"vigilan\w*",
        r"strong\w*", r"robust", r"solid", r"tight labor", r"labor markets? (?:remain(?:ed|s)? )?tight", r"elevated inflation",
        r"inflation (?:remains?|remained) elevated", r"reduce (?:the size of )?(?:its|the) (?:securities holdings|balance sheet)",
        r"reduc\w+ (?:in )?(?:the pace of )?(?:asset |securities )?purchases", r"taper\w*", r"restrictive", r"further (?:policy )?firming",
        r"additional firming", r"price stability"]
DOVE = [r"weak\w*", r"slow\w*", r"downside risks?", r"accommodat\w*", r"eas(?:e|ed|ing)\b", r"lower\w*", r"declin\w*",
        r"deteriorat\w*", r"stimul\w*", r"(?:asset|securities|treasury|mortgage-backed) purchases", r"subdued", r"low inflation",
        r"patient", r"exceptionally low", r"extended period", r"strains?", r"stress\w*", r"uncertain\w*",
        r"unemployment (?:rate )?(?:remains?|remained) elevated", r"slack", r"soft\w*", r"moderat\w*", r"disinflation\w*",
        r"economic weakness", r"reduc\w+ (?:in )?the (?:target|federal funds rate)", r"cut\w*"]
HRE = re.compile("|".join(r"\b" + h for h in HAWK), re.I)
DRE = re.compile("|".join(r"\b" + d for d in DOVE), re.I)
WORD = re.compile(r"[a-z]{3,}")


def dict_scores(t):
    h, d = len(HRE.findall(t)), len(DRE.findall(t))
    n = max(len(t.split()), 1)
    return h, d, (h - d) / (h + d + 1.0), (h + d) / n


def cosine(a, b):
    ca, cb = collections.Counter(WORD.findall(a.lower())), collections.Counter(WORD.findall(b.lower()))
    num = sum(ca[w] * cb.get(w, 0) for w in ca)
    den = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return num / den if den else np.nan


def main():
    m = pd.read_csv(D / "meetings.csv", parse_dates=["stmt_date", "decision_date", "minutes_release"])
    px = pd.read_parquet(D / "prices.parquet")
    tdays = px.index
    names = tp.build_surnames(f.read_text() for f in sorted((D / "docs").glob("*.txt")))
    print("surnames stripped:", len(names))
    (D / "surnames.txt").write_text("\n".join(names))
    rows = []
    for _, r in m.iterrows():
        if isinstance(r.statement_url, str):
            f = D / "docs" / f"stmt_{r.decision_date:%Y%m%d}.txt"
            if f.exists():
                raw = f.read_text()
                body, votes = tp.split_votes(tp.statement_body(raw))
                rows.append(dict(kind="S", doc_date=r.decision_date, release=r.decision_date, header=r.header,
                                 text=tp.anonymise(body), dissents=tp.count_dissents_statement(votes) if votes else np.nan,
                                 n_raw=len(raw)))
        if isinstance(r.minutes_url, str) and pd.notna(r.minutes_release):
            ds = re.search(r"((?:19|20)\d{6})", r.minutes_url)
            f = D / "docs" / f"min_{ds.group(1) if ds else f'{r.decision_date:%Y%m%d}'}.txt"
            if f.exists():
                raw = f.read_text()
                rows.append(dict(kind="M", doc_date=r.decision_date, release=r.minutes_release, header=r.header,
                                 text=tp.anonymise(tp.clean_minutes(tp.minutes_body(raw))),
                                 dissents=tp.count_dissents_minutes(raw), n_raw=len(raw)))
    d = pd.DataFrame(rows).drop_duplicates(["kind", "release"]).sort_values(["release", "kind"]).reset_index(drop=True)
    d = d[d.text.str.len() > 100].reset_index(drop=True)
    # event (trading) date
    pos = tdays.searchsorted(d.release)
    d["event_date"] = [tdays[p] if p < len(tdays) else pd.NaT for p in pos]
    d = d[d.event_date.notna()].reset_index(drop=True)
    # dictionary features and diffs vs previous doc of the same kind
    sc = d.text.apply(dict_scores)
    d["dict_h"], d["dict_d"], d["dict_net"], d["dict_density"] = zip(*sc)
    d["prev_text"] = d.groupby("kind").text.shift(1)
    d["dict_dnet"] = d.dict_net - d.groupby("kind").dict_net.shift(1)
    d["cos_prev"] = [cosine(a, b) if isinstance(b, str) else np.nan for a, b in zip(d.text, d.prev_text)]
    d["dissents"] = d.dissents.fillna(0)
    # (a) market reaction on the event day (known by the close)
    i = tdays.get_indexer(d.event_date)
    d["dy2_bp"] = (px.DGS2.values[i] - px.DGS2.values[i - 1]) * 100
    d["spy_day"] = px.SPY_cc.values[i]
    d["tlt_day"] = px.TLT_cc.values[i]
    d["period"] = np.where(d.event_date <= "2012-12-31", "DEV", "TEST")
    d.to_parquet(D / "docs.parquet")
    print(d.groupby(["period", "kind"]).size())
    print(d.groupby("kind")[["dict_net", "dict_dnet", "cos_prev", "dissents", "dy2_bp", "spy_day"]].describe().T.round(3))
    print("text length by kind (chars):", d.groupby("kind").text.apply(lambda s: s.str.len().describe()[["mean", "max"]]).round(0).to_dict())


if __name__ == "__main__":
    main()
