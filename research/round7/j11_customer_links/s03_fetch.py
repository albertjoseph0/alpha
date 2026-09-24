"""Fetch 10-K primary documents from the queue (DATA/fetch_queue.csv, re-read every 25 docs so stage 2 can be
appended while running), extract candidate major-customer sentences + candidate names (regex, extract.py), and
append them to DATA/cands.jsonl.  Documents are fetched with cache=False (nothing big is stored).  Resumable."""
import json
import time
from common import *
from extract import extract
from secx import fetch

QF, OUTF = DATA / "fetch_queue.csv", DATA / "cands.jsonl"


def done_set():
    s = set()
    if OUTF.exists():
        for line in open(OUTF):
            try:
                s.add(json.loads(line)["acc"])
            except Exception:
                pass
    return s


def main():
    done = done_set()
    t0, n = time.time(), 0
    while True:
        Q = pd.read_csv(QF).sort_values(["prio", "filing_date"])
        todo = Q[~Q.acc.isin(done)]
        if todo.empty:
            break
        for r in todo.head(25).itertuples():
            url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.acc.replace('-', '')}/{r.primary}"
            rec = {"acc": r.acc, "cik": int(r.cik), "stage": int(r.stage)}
            try:
                h = fetch(url)
                text, res = extract(h)
                rec.update(len=len(text), sents=[[s, c] for s, c in res])
            except Exception as e:  # 404 etc.: record and move on
                rec.update(err=str(e)[:200], sents=[])
            with open(OUTF, "a") as f:
                f.write(json.dumps(rec) + "\n")
            done.add(r.acc)
            n += 1
            if n % 25 == 0:
                print(n, len(done), len(Q), r.acc, round(time.time() - t0), flush=True)
    print("queue empty", n, round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
