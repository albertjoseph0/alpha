"""Score every fetched 8-K in [START, END] with a frozen Jev question set.
Usage: s04_jev.py START END VERSION  -> DATA/jev_<VERSION>.jsonl.gz (resumable; Jev responses are cached)."""
import gzip, json, sys, time
import pandas as pd
from common import AGENT, DATA, read_texts
from state import build_state
import j02_questions as JQ
from jev import ask, spent, BudgetExceeded

start, end, ver = sys.argv[1], sys.argv[2], sys.argv[3]
Q = getattr(JQ, "Q_" + ver.upper())
ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate"]).set_index("accessionNumber")
out = DATA / f"jev_{ver}.jsonl.gz"
done = set()
if out.exists():
    for r in read_texts(out):
        done.add(r["acc"])
    # rewrite cleanly in case the tail was truncated
    good = read_texts(out)
    with gzip.open(out, "wt") as fo:
        for r in good:
            fo.write(json.dumps(r) + "\n")
n, t0 = 0, time.time()
with gzip.open(out, "at") as fo:
    for rec in read_texts():
        e = ev.loc[rec["acc"]]
        if rec["acc"] in done or not (pd.Timestamp(start) <= e.filingDate <= pd.Timestamp(end)):
            continue
        st = build_state(rec, e)
        try:
            a = ask(st, Q, agent=AGENT)
        except BudgetExceeded as ex:
            print("BUDGET", ex); break
        except Exception as ex:
            print("err", rec["acc"], str(ex)[:200], flush=True); continue
        fo.write(json.dumps({"acc": rec["acc"], "nstate": len(st), "a": a}) + "\n")
        n += 1
        if n % 500 == 0:
            fo.flush(); print(n, e.filingDate.date(), round(time.time() - t0), spent(AGENT), flush=True)
print("done", n, spent(AGENT), flush=True)
