"""Jev features for each 8-K 2.02 press release (filed 2020-01 onward).
State = anonymised narrative of the CURRENT release (<=12k chars) + the same company's PREVIOUS release
(<=8k chars; only if accepted within 200 days before). Questions frozen in jev_questions.py.
Streams texts_all.jsonl.gz (sorted by filing date), resumable via Jev's on-disk cache.
Usage: s07_jev.py [MAX_DATE]   -> DATA/jev_raw.jsonl.gz (acc -> answers) and DATA/jev_features.parquet"""
import sys, gzip, json, time
import pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5")
from jev import ask, spent, BudgetExceeded
from textprep import name_patterns, anonymise, narrative
from jev_questions import QUESTIONS
from common import DATA

MAX_DATE = sys.argv[1] if len(sys.argv) > 1 else "2099-01-01"
START = "2020-01-01"
ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate", "accept_et"]).set_index("accessionNumber")
last = {}   # cik -> (accept_et, anonymised narrative)
out = []
t0 = time.time(); n_new = 0
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
        pats = name_patterns(r.company, r["name"], r.ticker)
        cur = anonymise(narrative(d["text"], 12000), pats)
        prev = last.get(r.cik)
        has_prev = prev is not None and 20 <= (r.accept_et - prev[0]).days <= 200
        last[r.cik] = (r.accept_et, cur)
        if r.filingDate < pd.Timestamp(START) or r.filingDate > pd.Timestamp(MAX_DATE):
            continue
        if len(cur) < 200:
            out.append({"acc": d["acc"], "has_prev": has_prev, "ok": False}); continue
        state = "CURRENT RELEASE:\n" + cur + "\n\nPREVIOUS RELEASE:\n" + (prev[1][:8000] if has_prev else "(not provided)")
        try:
            a = ask(state, QUESTIONS, agent="m06")
        except BudgetExceeded:
            print("BUDGET EXCEEDED", flush=True); break
        except Exception as e:
            print("error", d["acc"], str(e)[:200], flush=True); continue
        out.append({"acc": d["acc"], "has_prev": has_prev, "ok": True, "ans": a})
        n_new += 1
        if n_new % 250 == 0:
            print(n_new, r.filingDate.date(), round(time.time() - t0), spent("m06"), flush=True)
except (EOFError, OSError):
    pass
with gzip.open(DATA / "jev_raw.jsonl.gz", "wt") as fo:
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
F.to_parquet(DATA / "jev_features.parquet")
print("done", len(F), "ok", int(F.jev_ok.sum()), "spent", spent("m06"), round(time.time() - t0))
