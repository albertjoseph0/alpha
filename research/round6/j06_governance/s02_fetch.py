"""Fetch proxy primary documents (via the shared rate-limited sec.get, not cached in the shared cache to save
disk), convert HTML -> plain text, and keep the first candidate per firm-season (latest first) that is an
annual-meeting proxy: it must contain a CD&A and a summary compensation table.

Stores DATA/text/<fid>.txt.gz (full plain text) and appends to DATA/fetched.csv
(fid, acc, form, accept, n_chars, ok, reason). Resumable.

usage: s02_fetch.py pilot|dev|all [limit]"""
import gzip
import re
import sys
import time
import lxml.html
from concurrent.futures import ThreadPoolExecutor
from common import *
from sec import get

TXT = DATA / "text"
TXT.mkdir(exist_ok=True)
LOG = DATA / "fetched.csv"
BLOCK = ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "center", "section", "font")


def html2text(html: str) -> str:
    html = re.sub(r"^<\?xml[^>]*>", "", html.lstrip())
    try:
        root = lxml.html.fromstring(html)
    except Exception:
        return ""
    for el in root.xpath('//script|//style|//head|//*[contains(translate(@style," ",""),"display:none")]'):
        el.drop_tree()
    for el in root.iter("td", "th"):
        el.tail = " | " + (el.tail or "")
    for el in root.iter(*BLOCK):
        if el.tag == "font":
            continue
        el.tail = "\n" + (el.tail or "")
    t = root.text_content()
    t = t.replace("\xa0", " ").replace("​", "").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"(\| *){2,}", "| ", t)
    lines = [re.sub(r"^[|\s]+|[|\s]+$", "", ln) for ln in t.split("\n")]
    t = "\n".join(lines)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def is_annual(t: str):
    low = t.lower()
    cda = re.search(r"compensation\s+discussion\s*(and|&)\s*analysis", low) is not None
    sct = re.search(r"summary\s+compensation\s+table", low) is not None
    if len(t) < 60000:
        return False, f"short:{len(t)}"
    if not (cda and sct):
        return False, f"cda={cda},sct={sct}"
    return True, ""


def main():
    mode = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    CD = pd.read_csv(DATA / "candidates.csv")
    fids = CD.fid.drop_duplicates()
    if mode == "pilot":
        U = pd.read_csv(DATA / "universe.csv")
        fids = U[U.season.isin(DEV_SEASONS) & U.fid.isin(fids)].sample(200, random_state=6).fid
    elif mode == "dev":
        fids = CD[CD.season.isin(DEV_SEASONS)].fid.drop_duplicates()
    if limit:
        fids = fids.iloc[:limit]
    done = set(pd.read_csv(LOG).fid) if LOG.exists() else set()
    todo = [f for f in fids if f not in done]
    print(mode, "todo", len(todo), "done", len(done), flush=True)
    t0 = time.time()

    def work(fid):
        cands = CD[CD.fid == fid].sort_values("rank")
        rec = dict(fid=fid, acc=None, form=None, accept=None, n_chars=0, ok=False, reason="", tried=0)
        for x in cands.itertuples():
            url = f"https://www.sec.gov/Archives/edgar/data/{int(x.cik)}/{x.acc.replace('-', '')}/{x.primary}"
            rec["tried"] += 1
            try:
                html = get(url, cache=False)
            except Exception as e:
                rec["reason"] += f"|fetch {x.acc}: {str(e)[:60]}"
                continue
            t = html2text(html)
            ok, why = is_annual(t)
            if ok:
                (TXT / f"{fid}.txt.gz").write_bytes(gzip.compress(t.encode()))
                rec.update(acc=x.acc, form=x.form, accept=x.accept, n_chars=len(t), ok=True)
                break
            rec["reason"] += f"|{x.acc}:{why}"
            if rec["tried"] >= 4:
                break
        return rec

    with ThreadPoolExecutor(3) as ex:
        for n, rec in enumerate(ex.map(work, todo)):
            pd.DataFrame([rec]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
            if n % 25 == 0:
                print(n, rec["fid"], rec["ok"], rec["n_chars"], rec["reason"][:80], round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
