"""Pair each filing with the same firm's filing one year earlier (10-K vs prior 10-K; 10-Q vs the 10-Q for the same
fiscal quarter a year earlier, report dates 365 +/- 45 days apart), compute classic similarity features (set b),
LM tone, and the paragraph diff -> anonymised Jev state. Output: DATA/pairs.parquet, DATA/states.jsonl.gz.
Re-runnable: recomputes everything from DATA/sections (cheap)."""
import gzip
import json
import time
import pysentiment2 as ps
from common import *
from compare import sim_features, para_diff, jev_state, words, SECS

SD = DATA / "sections"
MAXC = {"rf": 14000, "mda": 14000, "legal": 5000}   # chars per section in the Jev state (~8k tokens max total)
lm = ps.LM()
subs = pd.read_csv(DATA / "submissions_rows.csv", usecols=["cik", "name"]).drop_duplicates("cik")
NAME = dict(zip(subs.cik, subs.name))


def lm_neg(t):
    if not t:
        return math.nan
    tok = lm.tokenize(t[:60000])
    sc = lm.get_score(tok)
    return sc["Negative"] / max(len(tok), 1), sc["Positive"] / max(len(tok), 1)


import math


def load(f):
    recs = []
    with gzip.open(f, "rt") as fh:
        try:
            for ln in fh:
                try:
                    recs.append(json.loads(ln))
                except Exception:
                    pass
        except (EOFError, OSError):
            pass
    return recs


rows = []
t0 = time.time()
with gzip.open(DATA / "states.jsonl.gz", "wt", compresslevel=6) as out:
    for k, f in enumerate(sorted(SD.glob("*.jsonl.gz"))):
        recs = {r["acc"]: r for r in load(f)}
        R = pd.DataFrame([{"acc": a, "form": r["form"], "fd": pd.Timestamp(r["filing_date"]),
                           "rd": pd.to_datetime(r["report_date"], errors="coerce")} for a, r in recs.items()])
        if R.empty:
            continue
        R["kind"] = np.where(R.form.str.startswith("10-K"), "K", "Q")
        for r in R.itertuples():
            cand = R[(R.kind == r.kind) & (R.fd < r.fd)]
            if r.kind == "K":
                cand = cand[((r.fd - cand.fd).dt.days).between(270, 450)]
                if len(cand):
                    cand = cand.iloc[[np.argmin(np.abs((r.fd - cand.fd).dt.days - 365))]]
            else:
                ref = r.rd if pd.notna(r.rd) else r.fd
                cr = cand.rd.fillna(cand.fd)
                cand = cand[((ref - cr).dt.days).between(320, 410)]
                if len(cand):
                    cand = cand.iloc[[np.argmin(np.abs((ref - cand.rd.fillna(cand.fd)).dt.days - 365))]]
            if not len(cand):
                continue
            cur, pri = recs[r.acc], recs[cand.acc.iloc[0]]
            feat = sim_features(cur, pri)
            diffs = {}
            for s in SECS:
                new, gone, st = para_diff(cur.get(s, ""), pri.get(s, ""))
                diffs[s] = (new, gone, bool(pri.get(s)), bool(cur.get(s)))
                feat.update({f"{s}_{kk}": v for kk, v in st.items()})
            for s in ("rf", "mda"):
                nc = lm_neg(cur.get(s, ""))
                npr = lm_neg(pri.get(s, ""))
                feat[f"lmneg_{s}"] = nc[0] if nc == nc else math.nan
                if isinstance(nc, tuple) and isinstance(npr, tuple):
                    feat[f"dlmneg_{s}"] = nc[0] - npr[0]
                    feat[f"dlmpos_{s}"] = nc[1] - npr[1]
                else:
                    feat[f"dlmneg_{s}"] = math.nan
                    feat[f"dlmpos_{s}"] = math.nan
            state = jev_state(diffs, cur["form"], NAME.get(cur["cik"]), cur.get("ticker"), MAXC)
            sj = json.dumps(state, ensure_ascii=False)
            feat.update({"acc": r.acc, "prior_acc": cand.acc.iloc[0], "cik": cur["cik"], "ticker": cur["ticker"],
                         "form": cur["form"], "filing_date": cur["filing_date"], "accept": cur["accept"],
                         "state_chars": len(sj)})
            rows.append(feat)
            out.write(json.dumps({"acc": r.acc, "state": sj}) + "\n")
        if k % 50 == 0:
            print(k, len(rows), round(time.time() - t0), flush=True)
P = pd.DataFrame(rows)
P.to_parquet(DATA / "pairs.parquet")
print("pairs:", len(P), P.groupby(P.form.str[:4]).size().to_dict())
print(P.describe().T.to_string())
