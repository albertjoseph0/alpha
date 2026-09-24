"""Ask Jev the question set about each letter's redacted state (one call per letter, all questions at once).
usage: python s05_jev.py <set: v1|leak> <from_dissem YYYY-MM-DD> <to_dissem YYYY-MM-DD> [max_n] [threads]
Reads DATA/letters.parquet (s04). Output: DATA/jev_<set>.parquet (flattened answers; merged with earlier runs) and
DATA/jev_<set>_raw.jsonl.gz (raw answers). Cached by jev.py, so re-runs are free. Threads only overlap network
waits (no CPU work); the spend ledger is protected by a lock."""
import gzip
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from common import *
import jev
from questions import Q_V1, Q_LEAK, make_state

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
            for c in q["criteria"]:
                out[f"j_{k}_{c}"] = p.get(c, np.nan)
            out[f"j_{k}"] = a.get("choice")
            out[f"jc_{k}"] = a.get("confidence", np.nan)
    return out


def main():
    qset = sys.argv[1]
    d0, d1 = pd.Timestamp(sys.argv[2]), pd.Timestamp(sys.argv[3])
    max_n = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    nthr = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    qs = {"v1": Q_V1, "leak": Q_LEAK}[qset]
    L = pd.read_parquet(DATA / "letters.parquet", columns=["acc", "dissem", "forms", "body", "image_pdf"])
    L = L[(L.dissem >= d0) & (L.dissem <= d1) & ~L.image_pdf & (L.body.str.len() > 20)]
    if qset == "leak":  # probe sample: fixed list chosen by s06_leak.py
        want = pd.read_csv(DATA / "leak_sample.csv").acc
        L = L[L.acc.isin(want)]
    if max_n:
        L = L.sample(min(max_n, len(L)), random_state=7)
    f = DATA / f"jev_{qset}.parquet"
    have = set(pd.read_parquet(f).acc) if f.exists() else set()
    L = L[~L.acc.isin(have)]
    todo = list(zip(L.acc, [make_state(list(fm), b) for fm, b in zip(L.forms, L.body)]))
    print(qset, "calls:", len(todo), "spent so far:", jev.spent(AGENT), flush=True)
    t0 = time.time()
    res, raw = {}, []

    def one(item):
        a, st = item
        try:
            return a, jev.ask(st, qs, agent=AGENT)
        except jev.BudgetExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            print("fail", a, str(e)[:200], flush=True)
            return a, None

    def save():
        J = pd.DataFrame.from_dict(res, orient="index")
        J.index.name = "acc"
        J = J.reset_index()
        if f.exists():
            old = pd.read_parquet(f)
            J = pd.concat([old[~old.acc.isin(J.acc)], J])
        J.to_parquet(f)
        with gzip.open(DATA / f"jev_{qset}_raw.jsonl.gz", "at") as fh:
            for a, ans in raw:
                fh.write(json.dumps({"acc": a, "ans": ans}) + "\n")
        raw.clear()
        return len(J)

    with ThreadPoolExecutor(nthr) as ex:
        for i, (a, ans) in enumerate(ex.map(one, todo)):
            if ans is not None:
                res[a] = flatten(ans, qs)
                raw.append((a, ans))
            if i % 200 == 199:
                n = save()
                print(i + 1, round(time.time() - t0), "saved", n, jev.spent(AGENT), flush=True)
    n = save()
    print("saved", n, "spent:", jev.spent(AGENT), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
