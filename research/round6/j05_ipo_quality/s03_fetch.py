"""Fetch each candidate's 424B4 primary document, convert to text, store gzipped text per filing
(data/.../txt/<acc>.txt.gz). Raw HTML is not cached (cache=False) to save disk.
Usage: s03_fetch.py [limit]"""
import sys, re, gzip, html as H
import pandas as pd
from lxml import html as LH
from common import DATA, get

TXT = DATA / "txt"; TXT.mkdir(exist_ok=True)
c = pd.read_csv(DATA / "candidates.csv", parse_dates=["date"])
c = c[~c.spac_name].sort_values("date")
lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
if lim:
    c = c.sample(lim, random_state=1)


def to_text(b):
    try:
        doc = LH.fromstring(b)
    except Exception:
        return re.sub(r"<[^>]+>", " ", b)
    for bad in doc.xpath("//script|//style"):
        bad.drop_tree()
    for td in doc.xpath("//td|//th"):
        td.tail = (td.tail or "") + " | "
    for br in doc.xpath("//br|//p|//div|//tr|//li|//h1|//h2|//h3|//h4|//table"):
        br.tail = (br.tail or "") + "\n"
    t = doc.text_content().replace("\xa0", " ").replace("​", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"(\s*\|\s*)+\n", " |\n", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


log = []
for i, r in enumerate(c.itertuples()):
    out = TXT / f"{r.acc}.txt.gz"
    if out.exists():
        continue
    nd = r.acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{nd}/"
    try:
        idx = get(base + r.acc + "-index.htm")
        docs = re.findall(r'<tr[^>]*>(.*?)</tr>', idx, re.S | re.I)
        href = None
        for row in docs:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
            if len(cells) >= 4 and "424B4" in re.sub("<[^>]+>", "", cells[3]).upper():
                m = re.search(r'href="([^"]+)"', cells[2])
                if m:
                    href = m.group(1); break
        if href is None:
            m = re.search(r'href="(/Archives/edgar/data/[^"]+\.(?:htm|html|txt))"', idx)
            href = m.group(1) if m else None
        if href is None:
            log.append((r.acc, "nodoc")); continue
        href = href.replace("/ix?doc=", "")
        raw = get("https://www.sec.gov" + href if href.startswith("/") else base + href, cache=False)
        txt = to_text(raw) if re.search(r"<html|<body|<div|<p[ >]", raw[:5000], re.I) else raw
        out.write_bytes(gzip.compress(txt.encode()))
    except Exception as e:
        log.append((r.acc, f"err {e}"[:200]))
    if i % 50 == 0:
        print(i, r.date.date(), r.company, flush=True)
pd.DataFrame(log, columns=["acc", "msg"]).to_csv(DATA / f"fetch_log_{lim or 'all'}.csv", index=False)
print("done; errors", len(log))
