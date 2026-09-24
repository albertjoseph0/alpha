"""Threaded version of s02_fetch_text.py (EDGAR latency is ~1.5-2 s per request regardless of size, so a few I/O
threads in one process are needed; the shared sec.get file lock still caps the global rate).
Fetches every event not yet in any texts*.jsonl.gz, DEV dates first, into texts_x.jsonl.gz.
Usage: s02b_fetch_threads.py NTHREADS"""
import gzip, json, sys, time, urllib.error
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from common import DATA, get, read_texts
import s02_fetch_text as S  # reuse to_text/body_core (module guarded below)

N = int(sys.argv[1])
ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate"]).sort_values("filingDate")
done = {r["acc"] for r in read_texts()}
outp = DATA / "texts_x.jsonl.gz"
good = read_texts(outp)
done |= {r["acc"] for r in good}
with gzip.open(outp, "wt") as fo:  # rewrite cleanly (drops a truncated tail)
    for r in good:
        fo.write(json.dumps(r) + "\n")
todo = [r for r in ev.itertuples() if r.accessionNumber not in done]
print("todo", len(todo), flush=True)


def work(r):
    acc = r.accessionNumber
    url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{acc.replace('-', '')}/{acc}.txt"
    try:
        raw = get(url, cache=False)
    except urllib.error.HTTPError as e:
        raw = ""
    except Exception as e:
        return None
    body, ex, extype, ex10 = "", "", None, []
    for d in S.RE_DOC.findall(raw):
        m = S.re.search(r"<TYPE>([^\n<]+)", d)
        typ = m.group(1).strip().upper() if m else ""
        tm = S.re.search(r"<TEXT>(.*?)</TEXT>", d, S.re.S)
        txt = tm.group(1) if tm else ""
        if typ.startswith("8-K") and not body:
            body = S.body_core(S.to_text(txt))
        elif typ.startswith("EX-99") and not ex:
            ex, extype = S.to_text(txt), typ
        elif typ.startswith(("EX-10", "EX-2.", "EX-1.")):
            ex10.append(typ)
    return {"acc": acc, "body": body[:25000], "ex": ex[:25000], "extype": extype,
            "nbody": len(body), "nex": len(ex), "other_ex": ex10}


n, t0 = 0, time.time()
with gzip.open(outp, "at") as fo, ThreadPoolExecutor(N) as pool:
    for i in range(0, len(todo), 200):
        for rec in pool.map(work, todo[i:i + 200]):
            if rec is not None:
                fo.write(json.dumps(rec) + "\n"); n += 1
        fo.flush()
        print(n, todo[min(i + 199, len(todo) - 1)].filingDate.date(), round(n / (time.time() - t0), 2), "/s", flush=True)
print("done", n, flush=True)
