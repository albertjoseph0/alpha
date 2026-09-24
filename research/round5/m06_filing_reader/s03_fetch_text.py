"""Fetch the earnings press release (EX-99.1, else first EX-99.x, else the 8-K body) for each
Item 2.02 8-K and store cleaned text (first 30k chars). Usage: s03_fetch_text.py START END OUT"""
import sys, re, json, gzip, html as H
import pandas as pd
from lxml import html as LH
from common import DATA, fetch

start, end, out = sys.argv[1], sys.argv[2], sys.argv[3]
ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate"])
ev = ev[(ev.filingDate >= start) & (ev.filingDate <= end)].sort_values("filingDate")
outp = DATA / out
done = set()
if outp.exists():
    with gzip.open(outp, "rt") as f:
        for line in f:
            done.add(json.loads(line)["acc"])
print("events", len(ev), "already", len(done), flush=True)


def to_text(b):
    try:
        doc = LH.fromstring(b)
    except Exception:
        return ""
    for bad in doc.xpath("//script|//style|//ix:header", namespaces={"ix": "http://www.xbrl.org/2013/inlineXBRL"}):
        bad.drop_tree()
    # keep table cells separated
    for td in doc.xpath("//td|//th"):
        td.tail = (td.tail or "") + " | "
    for br in doc.xpath("//br|//p|//div|//tr|//li"):
        br.tail = (br.tail or "") + "\n"
    t = doc.text_content()
    t = t.replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


n = 0
with gzip.open(outp, "at") as fo:
    for r in ev.itertuples():
        if r.accessionNumber in done:
            continue
        acc = r.accessionNumber; nd = acc.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{nd}/"
        idx = fetch(base + acc + "-index.htm")
        doc_url, dtype = None, None
        if idx:
            try:
                t = LH.fromstring(idx.encode())
                rows = t.xpath("//table[@class='tableFile']//tr")
                cands = []
                for tr in rows:
                    tds = tr.xpath("./td")
                    if len(tds) >= 4:
                        typ = tds[3].text_content().strip().upper()
                        a = tds[2].xpath(".//a/@href")
                        if a and typ.startswith("EX-99") and a[0].lower().endswith((".htm", ".html", ".txt")):
                            cands.append((0 if typ in ("EX-99.1", "EX-99.01", "EX-99") else 1, typ, a[0]))
                if cands:
                    cands.sort(); dtype = cands[0][1]
                    doc_url = "https://www.sec.gov" + cands[0][2].replace("/ix?doc=", "")
            except Exception as e:
                pass
        if doc_url is None:
            doc_url, dtype = base + r.primaryDocument, "8-K"
        b = fetch(doc_url, cache=False, binary=True)
        text = to_text(b) if b else ""
        fo.write(json.dumps({"acc": acc, "doc": doc_url, "dtype": dtype, "nchar": len(text), "text": text[:30000]}) + "\n")
        n += 1
        if n % 200 == 0:
            fo.flush(); print(n, r.filingDate.date(), dtype, len(text), flush=True)
print("done", n)
