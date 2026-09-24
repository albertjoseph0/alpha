"""Fetch each 8-K's full submission .txt (one EDGAR request, not cached by sec.get to save disk), keep the
8-K body (cover page and signature stripped) and the first EX-99.x press release as clean text.
Usage: s02_fetch_text.py START END [OUT]  -> appends to DATA/OUT (default texts.jsonl.gz) (resumable, truncation-safe)."""
import gzip, json, re, sys, urllib.error
import pandas as pd
from lxml import html as LH
from common import DATA, get

RE_DOC = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.S)


def to_text(s):
    if "<html" not in s[:5000].lower() and "<div" not in s[:5000].lower() and "<p" not in s[:5000].lower():
        return re.sub(r"[ \t]+", " ", s).strip()
    try:
        doc = LH.fromstring(s.encode("utf-8", "replace"))
    except Exception:
        return ""
    for bad in doc.xpath("//script|//style|//*[local-name()='header']"):
        bad.drop_tree()
    for td in doc.xpath("//td|//th"):
        td.tail = (td.tail or "") + " | "
    for br in doc.xpath("//br|//p|//div|//tr|//li"):
        br.tail = (br.tail or "") + "\n"
    t = doc.text_content().replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def body_core(t):
    """Drop the 8-K cover page (everything before the first 'Item x.xx' after the checkbox block) and the
    signature block."""
    m = re.search(r"emerging growth company.{0,600}?(?=Item\s*\d\.\d\d)", t, re.I | re.S)
    if m:
        t = t[m.end():]
    else:
        m = re.search(r"Item\s*\d\.\d\d", t, re.I)
        if m:
            t = t[m.start():]
    m = re.search(r"\n\s*SIGNATURES?\s*\n", t)
    if m:
        t = t[:m.start()]
    return t.strip()



if __name__ == "__main__":
    start, end = sys.argv[1], sys.argv[2]
    ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate"])
    ev = ev[(ev.filingDate >= start) & (ev.filingDate <= end)].sort_values("filingDate")
    outp = DATA / (sys.argv[3] if len(sys.argv) > 3 else "texts.jsonl.gz")
    done, good, corrupt = set(), [], False
    if outp.exists():
        try:
            with gzip.open(outp, "rt") as f:
                for line in f:
                    try:
                        done.add(json.loads(line)["acc"]); good.append(line)
                    except json.JSONDecodeError:
                        corrupt = True
        except (EOFError, OSError):
            corrupt = True
        if corrupt:
            tmp = outp.with_suffix(".rescue")
            with gzip.open(tmp, "wt") as fo:
                fo.writelines(good)
            tmp.replace(outp); print("rescued", len(good), flush=True)
    print("events", len(ev), "already", len(done), flush=True)


    n = 0
    with gzip.open(outp, "at") as fo:
        for r in ev.itertuples():
            if r.accessionNumber in done:
                continue
            acc = r.accessionNumber
            url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{acc.replace('-', '')}/{acc}.txt"
            try:
                raw = get(url, cache=False)
            except urllib.error.HTTPError as e:
                raw = ""; print("http", e.code, acc, flush=True)
            except Exception as e:
                print("err", acc, e, flush=True); continue
            body, ex, extype, ex10 = "", "", None, []
            for d in RE_DOC.findall(raw):
                m = re.search(r"<TYPE>([^\n<]+)", d)
                typ = m.group(1).strip().upper() if m else ""
                tm = re.search(r"<TEXT>(.*?)</TEXT>", d, re.S)
                txt = tm.group(1) if tm else ""
                if typ.startswith("8-K") and not body:
                    body = body_core(to_text(txt))
                elif typ.startswith("EX-99") and not ex:
                    ex, extype = to_text(txt), typ
                elif typ.startswith(("EX-10", "EX-2.", "EX-1.")):
                    ex10.append(typ)
            fo.write(json.dumps({"acc": acc, "body": body[:25000], "ex": ex[:25000], "extype": extype,
                                 "nbody": len(body), "nex": len(ex), "other_ex": ex10}) + "\n")
            n += 1
            if n % 200 == 0:
                fo.flush(); print(n, r.filingDate.date(), len(body), len(ex), flush=True)
    print("done", n, flush=True)
