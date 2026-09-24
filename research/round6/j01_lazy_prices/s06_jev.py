"""Ask Jev the frozen question set about each pair's anonymised diff state (one call per filing, all questions).
usage: python s06_jev.py <set: V1|PROBE> <from_filing_date> <to_filing_date> [max_n] [threads]
Output: DATA/jev_<set>.parquet (flattened numeric answers; merged with any earlier file). Responses are cached by
jev.py, so re-runs are free. Threads only overlap network waits; the spend ledger is protected by a lock."""
import gzip
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from common import *
import jev
from questions import V1, PROBE

_lock = threading.Lock()
_orig = jev._record


def _locked(agent, tokens):
    with _lock:
        _orig(agent, tokens)


jev._record = _locked


def flatten(ans, qs):
    out = {}
    for k, q in qs.items():
        a = ans.get(k, {})
        if q["type"] == "noul":
            out[f"j_{k}"] = a.get("noul", np.nan)
        elif q["type"] == "score":
            out[f"j_{k}"] = a.get("score", np.nan)
            out[f"jc_{k}"] = a.get("confidence", np.nan)
        else:
            p = a.get("probabilities", {})
            ks = list(q["criteria"])
            out[f"j_{k}"] = p.get(ks[0], 0) - p.get(ks[-1], 0)
            out[f"jc_{k}"] = a.get("confidence", np.nan)
    return out


def main():
    qset = sys.argv[1]
    d0, d1 = sys.argv[2], sys.argv[3]
    max_n = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    nthr = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    qs = {"V1": V1, "PROBE": PROBE}[qset]
    P = pd.read_parquet(DATA / "pairs.parquet", columns=["acc", "filing_date", "form"])
    P = P[P.filing_date.between(d0, d1)]
    if qset == "PROBE":
        E = pd.read_parquet(DATA / "events.parquet", columns=["acc", "xret252", "form"])
        P = P[P.acc.isin(E[E.xret252.notna() & E.form.str.startswith("10-K")].acc)]
    if max_n:
        P = P.sample(min(max_n, len(P)), random_state=11)
    want = set(P.acc)
    states = {}
    with gzip.open(DATA / "states.jsonl.gz", "rt") as fh:
        for ln in fh:
            r = json.loads(ln)
            if r["acc"] in want:
                states[r["acc"]] = r["state"]
    todo = [a for a in P.acc if a in states]
    print(qset, "calls:", len(todo), "spent so far:", jev.spent(AGENT), flush=True)
    t0 = time.time()
    res = {}

    def one(a):
        try:
            return a, jev.ask(states[a], qs, agent=AGENT)
        except jev.BudgetExceeded:
            raise
        except Exception as e:
            print("fail", a, str(e)[:200], flush=True)
            return a, None

    with ThreadPoolExecutor(nthr) as ex:
        for i, (a, ans) in enumerate(ex.map(one, todo)):
            if ans is not None:
                res[a] = flatten(ans, qs)
            if i % 200 == 0:
                print(i, round(time.time() - t0), jev.spent(AGENT), flush=True)
    J = pd.DataFrame.from_dict(res, orient="index")
    J.index.name = "acc"
    J = J.reset_index()
    f = DATA / f"jev_{qset}.parquet"
    if f.exists():
        old = pd.read_parquet(f)
        J = pd.concat([old[~old.acc.isin(J.acc)], J])
    J.to_parquet(f)
    print("saved", len(J), "spent:", jev.spent(AGENT), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
