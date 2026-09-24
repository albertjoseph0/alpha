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
subs = pd.read_csv(DATA / "submissions_rows.csv", usecols=["cik", "name"]).drop_duplicates("cik")
NAME = dict(zip(subs.cik, subs.name))
PD = DATA / "pairs"
PD.mkdir(exist_ok=True)
lm = ps.LM()
_stem = lm._tokenizer._stemmer.stem
_stop = lm._tokenizer._stopset
_cache = {}


def _cls(w):
    c = _cache.get(w)
    if c is None:
        st = _stem(w)
        c = (0 if st in _stop else 1, st in lm._negset, st in lm._posset)
        _cache[w] = c
    return c


def lm_neg(t):
    """Loughran-McDonald negative/positive word shares (same stemming/stoplist as pysentiment2, but cached)."""
    if not t:
        return math.nan
    n = neg = pos = 0
    for w, k in Counter(re.findall(r"[a-z]+", t.lower())).items():
        keep, ng, ps_ = _cls(w)
        n += keep * k
        neg += ng * k
        pos += ps_ * k
    return neg / max(n, 1), pos / max(n, 1)


import math
import re
from collections import Counter


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


def process(f):
    """All pairs for one CIK; reuses already computed (acc, prior_acc) pairs from DATA/pairs/<cik>.*"""
    cik = f.name.split(".")[0]
    pf, sf = PD / f"{cik}.parquet", PD / f"{cik}.states.jsonl.gz"
    old, old_states = pd.DataFrame(), {}
    if pf.exists() and sf.exists():
        old = pd.read_parquet(pf)
        with gzip.open(sf, "rt") as fh:
            for ln in fh:
                d = json.loads(ln)
                old_states[d["acc"]] = d["state"]
    done = set(zip(old.acc, old.prior_acc)) if len(old) else set()
    recs = {r["acc"]: r for r in load(f)}
    R = pd.DataFrame([{"acc": a, "form": r["form"], "fd": pd.Timestamp(r["filing_date"]),
                       "rd": pd.to_datetime(r["report_date"], errors="coerce")} for a, r in recs.items()])
    if R.empty:
        return 0
    R["kind"] = np.where(R.form.str.startswith("10-K"), "K", "Q")
    rows, states, n_new = [], {}, 0
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
        pa = cand.acc.iloc[0]
        if (r.acc, pa) in done and r.acc in old_states:
            rows.append(old[old.acc == r.acc].iloc[0].to_dict())
            states[r.acc] = old_states[r.acc]
            continue
        cur, pri = recs[r.acc], recs[pa]
        feat = sim_features(cur, pri)
        diffs = {}
        for s in SECS:
            new, gone, st = para_diff(cur.get(s, ""), pri.get(s, ""))
            diffs[s] = (new, gone, bool(pri.get(s)), bool(cur.get(s)))
            feat.update({f"{s}_{kk}": v for kk, v in st.items()})
        for s in ("rf", "mda"):
            nc = lm_neg(cur.get(s, ""))
            npr = lm_neg(pri.get(s, ""))
            feat[f"lmneg_{s}"] = nc[0] if isinstance(nc, tuple) else math.nan
            ok = isinstance(nc, tuple) and isinstance(npr, tuple)
            feat[f"dlmneg_{s}"] = nc[0] - npr[0] if ok else math.nan
            feat[f"dlmpos_{s}"] = nc[1] - npr[1] if ok else math.nan
        state = jev_state(diffs, cur["form"], NAME.get(cur["cik"]), cur.get("ticker"), MAXC)
        sj = json.dumps(state, ensure_ascii=False)
        feat.update({"acc": r.acc, "prior_acc": pa, "cik": cur["cik"], "ticker": cur["ticker"],
                     "form": cur["form"], "filing_date": cur["filing_date"], "accept": cur["accept"],
                     "state_chars": len(sj)})
        rows.append(feat)
        states[r.acc] = sj
        n_new += 1
    if n_new:
        pd.DataFrame(rows).to_parquet(pf)
        with gzip.open(sf, "wt", compresslevel=6) as out:
            for a, sj in states.items():
                out.write(json.dumps({"acc": a, "state": sj}) + "\n")
    return n_new


t0 = time.time()
tot = 0
for k, f in enumerate(sorted(SD.glob("*.jsonl.gz"))):
    pf = PD / f"{f.name.split('.')[0]}.parquet"
    if pf.exists() and pf.stat().st_mtime > f.stat().st_mtime:
        continue
    tot += process(f)
    if k % 50 == 0:
        print(k, tot, round(time.time() - t0), flush=True)
P = pd.concat([pd.read_parquet(p) for p in sorted(PD.glob("*.parquet"))], ignore_index=True)
P.to_parquet(DATA / "pairs.parquet")
with gzip.open(DATA / "states.jsonl.gz", "wt", compresslevel=6) as out:
    for sf in sorted(PD.glob("*.states.jsonl.gz")):
        with gzip.open(sf, "rt") as fh:
            for ln in fh:
                out.write(ln)
print("new pairs:", tot, "all pairs:", len(P), P.groupby(P.form.str[:4]).size().to_dict(), round(time.time() - t0), "s")
print(P.describe().T.to_string())
