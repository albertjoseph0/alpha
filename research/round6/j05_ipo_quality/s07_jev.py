"""Run Jev question set on eligible IPO prospectuses. Usage: s07_jev.py QSET START END [leak]
Eligible: IPO text, not blank check/units, offer price >= $5 (or unknown). Answers appended to
jev_<qset>.jsonl (cached by jev.py, so re-runs are free). With 'leak', asks the forbidden probe
question instead (on a 200-doc DEV sample that has prices)."""
import sys, gzip, json, time
import pandas as pd
from common import DATA
from jev import ask, spent, BudgetExceeded
from jevq import QSETS, Q_LEAK, build_state

qset, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
leak = len(sys.argv) > 4 and sys.argv[4] == "leak"
m = pd.read_csv(DATA / "meta.csv", parse_dates=["date"])
m = m[m.ipo_text & ~m.blank_check & ~m.units & ~(m.offer_price < 5) & (m.date >= start) & (m.date <= end)]
if leak:
    pm = pd.read_csv(DATA / "price_map.csv")
    m = m[m.acc.isin(pm[pm.status == "ok"].acc)].sample(200, random_state=7)
secs = {}
with gzip.open(DATA / "sections.jsonl.gz", "rt") as f:
    for l in f:
        d = json.loads(l)
        if d["acc"] in set(m.acc):
            secs[d["acc"]] = d
out = DATA / (f"jev_leak.jsonl" if leak else f"jev_{qset}.jsonl")
done = set()
if out.exists():
    done = {json.loads(l)["acc"] for l in open(out)}
Q = Q_LEAK if leak else QSETS[qset]
n = 0
t0 = time.time()
with open(out, "a") as fo:
    for r in m.itertuples():
        if r.acc in done or r.acc not in secs:
            continue
        st = build_state(secs[r.acc], r.company, r.ticker)
        try:
            a = ask(st, Q, agent="j05")
        except BudgetExceeded as e:
            print("BUDGET", e); break
        except Exception as e:
            print("ERR", r.acc, str(e)[:200]); continue
        fo.write(json.dumps({"acc": r.acc, "nchar": len(st), "ans": a}) + "\n")
        n += 1
        if n % 50 == 0:
            fo.flush(); print(n, r.date.date(), spent("j05"), round(time.time() - t0), flush=True)
print("done", n, spent("j05"))
