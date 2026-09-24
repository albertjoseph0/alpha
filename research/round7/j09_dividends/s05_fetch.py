"""Fetch the matched 8-K document text for each event (the FTS-hit document, preferring EX-99.x press releases).
One EDGAR request per event via sec.get(cache=False); clean text (<=30k chars) appended to DATA/texts.jsonl.gz.
Resumable and truncation-safe. Usage: s05_fetch.py [START END]  (filters events on file_date)."""
import gzip, json, re, sys, urllib.error
import pandas as pd
from lxml import html as LH
from common import DATA, get


def to_text(s):
    low = s[:5000].lower()
    if "<html" not in low and "<div" not in low and "<p" not in low and "<table" not in low:
        return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
    try:
        doc = LH.fromstring(s.encode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return ""
    for bad in doc.xpath("//script|//style"):
        bad.drop_tree()
    for td in doc.xpath("//td|//th"):
        td.tail = (td.tail or "") + " | "
    for br in doc.xpath("//br|//p|//div|//tr|//li"):
        br.tail = (br.tail or "") + "\n"
    t = doc.text_content().replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def load_done(p):
    done = {}
    if p.exists():
        try:
            with gzip.open(p, "rt") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        done[r["adsh"]] = r
                    except json.JSONDecodeError:
                        break
        except (EOFError, OSError):
            pass
    return done


if __name__ == "__main__":
    ev = pd.read_parquet(DATA / "events_raw.parquet")
    if len(sys.argv) > 2:
        ev = ev[(ev.file_date >= sys.argv[1]) & (ev.file_date <= sys.argv[2])]
    outp = DATA / "texts.jsonl.gz"
    done = load_done(outp)
    if done and outp.exists():  # rewrite cleanly (drops any truncated tail)
        with gzip.open(outp, "wt") as fo:
            for r in done.values():
                fo.write(json.dumps(r) + "\n")
    todo = ev[~ev.adsh.isin(done)].sort_values("file_date")
    print("events", len(ev), "done", len(done), "todo", len(todo), flush=True)
    n = 0
    with gzip.open(outp, "at") as fo:
        for r in todo.itertuples():
            url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.adsh.replace('-', '')}/{r.file}"
            try:
                raw = get(url, cache=False)
            except urllib.error.HTTPError as e:
                raw = ""
                print("http", e.code, r.adsh, flush=True)
            except Exception as e:  # noqa: BLE001
                print("err", r.adsh, e, flush=True)
                continue
            t = to_text(raw)
            fo.write(json.dumps({"adsh": r.adsh, "file": r.file, "text": t[:30000], "n": len(t)}) + "\n")
            n += 1
            if n % 100 == 0:
                fo.flush()
                print(n, r.file_date, len(t), flush=True)
    print("done", n, flush=True)
