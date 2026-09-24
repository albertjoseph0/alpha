"""Jev features for each 8-K 2.02 press release (filed 2020-01 onward).
State = anonymised narrative of the CURRENT release (<=12k chars) + the same company's PREVIOUS release
(<=8k chars; only if accepted within 200 days before). Questions frozen in jev_questions.py.
Streams texts_all.jsonl.gz (sorted by filing date), resumable via Jev's on-disk cache.
Usage: s07_jev.py [MAX_DATE [START]]   -> DATA/jev_raw.jsonl.gz (acc -> answers) and DATA/jev_features.parquet
(with START given: DATA/jev_raw_START_MAX.jsonl.gz and DATA/jev_features_START_MAX.parquet; the previous-release
context is still built from all earlier texts)"""
import sys, gzip, json, time, random
import pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5")
from jev import ask, spent, BudgetExceeded
from textprep import name_patterns, anonymise, narrative
from jev_questions import QUESTIONS
from common import DATA

MAX_DATE = sys.argv[1] if len(sys.argv) > 1 else "2099-01-01"
START = sys.argv[2] if len(sys.argv) > 2 else "2020-01-01"
SUF = "" if len(sys.argv) <= 2 else f"_{START}_{MAX_DATE}"
ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate", "accept_et"]).set_index("accessionNumber")
import threading
from concurrent.futures import ThreadPoolExecutor
import jev as _jev
_lock = threading.Lock()
_orig_record = _jev._record
_jev._record = lambda agent, tokens: (_lock.acquire(), _orig_record(agent, tokens), _lock.release())
NTHREADS = int(__import__("os").environ.get("JEV_THREADS", "3"))   # network-bound I/O threads; negligible CPU

last = {}   # cik -> (accept_et, anonymised narrative)
jobs = []   # (acc, has_prev, state or None)
try:
    f = gzip.open(DATA / "texts_all.jsonl.gz", "rt")
    for line in f:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            break
        if d["acc"] not in ev.index:
            continue
        r = ev.loc[d["acc"]]
        if r.filingDate > pd.Timestamp(MAX_DATE):
            break   # file is in filing-date order
        pats = name_patterns(r.company, r["name"], r.ticker)
        cur = anonymise(narrative(d["text"], 12000), pats)
        prev = last.get(r.cik)
        has_prev = prev is not None and 20 <= (r.accept_et - prev[0]).days <= 200
        last[r.cik] = (r.accept_et, cur)
        if r.filingDate < pd.Timestamp(START) or r.filingDate > pd.Timestamp(MAX_DATE):
            continue
        if len(cur) < 200:
            jobs.append((d["acc"], has_prev, None)); continue
        state = "CURRENT RELEASE:\n" + cur + "\n\nPREVIOUS RELEASE:\n" + (prev[1][:8000] if has_prev else "(not provided)")
        jobs.append((d["acc"], has_prev, state))
except (EOFError, OSError):
    pass
del last
print("jobs", len(jobs), flush=True)
t0 = time.time(); stop = threading.Event(); cnt = [0]


def work(job):
    acc, hp, state = job
    if state is None:
        return {"acc": acc, "has_prev": hp, "ok": False}
    if stop.is_set():
        return {"acc": acc, "has_prev": hp, "ok": False, "err": "stopped"}
    try:
        for attempt in range(40):   # Jev returns fast 503s under load: retry quickly with jitter, not 2^k backoff
            try:
                a = ask(state, QUESTIONS, agent="m06", retries=1, timeout=60)
                break
            except RuntimeError as e:
                if ("503" in str(e) or "429" in str(e) or "502" in str(e)) and attempt < 39:
                    time.sleep(0.5 + random.random() * min(1 + attempt, 8)); continue
                raise
            except OSError:
                if attempt < 39:
                    time.sleep(2 + random.random() * 3); continue
                raise
    except BudgetExceeded:
        stop.set(); return {"acc": acc, "has_prev": hp, "ok": False, "err": "budget"}
    except Exception as e:
        print("error", acc, str(e)[:200], flush=True)
        return {"acc": acc, "has_prev": hp, "ok": False, "err": str(e)[:100]}
    with _lock:
        cnt[0] += 1
        if cnt[0] % 250 == 0:
            print(cnt[0], round(time.time() - t0), spent("m06"), flush=True)
    return {"acc": acc, "has_prev": hp, "ok": True, "ans": a}


with ThreadPoolExecutor(NTHREADS) as ex:
    out = list(ex.map(work, jobs))
with gzip.open(DATA / f"jev_raw{SUF}.jsonl.gz", "wt") as fo:
    for o in out:
        fo.write(json.dumps(o) + "\n")

# flatten
rows = []
for o in out:
    r = {"acc": o["acc"], "jev_has_prev": float(o["has_prev"]), "jev_ok": o["ok"]}
    for k, a in (o.get("ans") or {}).items():
        if a.get("type") == "noul":
            r[f"j_{k}"] = a["noul"]
        elif a.get("type") == "score":
            r[f"j_{k}"] = a["score"]
        elif a.get("type") == "choice":
            for opt, p in a["probabilities"].items():
                r[f"j_{k}__{opt}"] = p
    rows.append(r)
F = pd.DataFrame(rows)
F.to_parquet(DATA / f"jev_features{SUF}.parquet")
print("done", len(F), "ok", int(F.jev_ok.sum()), "spent", spent("m06"), round(time.time() - t0))
