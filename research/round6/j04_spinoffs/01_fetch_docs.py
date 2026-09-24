"""Step 1: pick, for every CIK in m08's EDGAR full-text hits that mentions when-issued/regular-way trading,
the latest information statement (EX-99.1 of the last Form 10 amendment, else the main Form 10 doc), fetch
it through the shared rate-limited `sec.get`, convert to plain text and store it gzipped in
data/round6/j04_spinoffs/text/<cik>.txt.gz. Writes data/round6/j04_spinoffs/docs.csv.
m08's files are read-only inputs."""
import gzip, os, re, sys
import pandas as pd
from bs4 import BeautifulSoup

ROOT = "/home/user/alpha"
sys.path.insert(0, f"{ROOT}/research/round5")
from sec import get  # noqa: E402

M08 = f"{ROOT}/data/round5/m08_spinoffs"
D = f"{ROOT}/data/round6/j04_spinoffs"
T = f"{D}/text"
os.makedirs(T, exist_ok=True)

e = pd.read_csv(f"{M08}/efts_hits.csv")
q = e.groupby("cik")["query"].apply(set)
keep = q[q.apply(lambda s: '"when-issued"' in s or '"regular-way"' in s)].index
e = e[e.cik.isin(keep)].drop_duplicates(["cik", "adsh", "fn"])
e = e[~e.fn.str.lower().str.endswith(".pdf")]


def pick(g):
    g = g.sort_values("date", ascending=False)
    for adsh, gg in g.groupby("adsh", sort=False):
        ex = gg[gg.ftype.isin(["EX-99.1", "EX-99", "EX-99.01"])]
        if len(ex):
            return ex.iloc[0]
        main = gg[gg.ftype.astype(str).str.startswith("10-12")]
        if len(main):
            return main.iloc[0]
    return None


rows = []
for cik, g in e.groupby("cik"):
    r = pick(g)
    if r is None:
        continue
    first = g.date.min()
    rows.append(dict(cik=cik, name=g.name.iloc[0], adsh=r.adsh, fn=r.fn, ftype=r.ftype, doc_date=r.date,
                     first_form10=first, root=r.root))
docs = pd.DataFrame(rows)
print(len(docs), "docs to fetch", flush=True)


def to_text(html: str) -> str:
    if "<html" in html[:5000].lower() or "<body" in html[:20000].lower() or "<p" in html[:20000].lower():
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style"]):
            t.decompose()
        txt = soup.get_text("\n")
    else:
        txt = html
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n\n", txt)
    return txt


ok = []
for i, r in docs.iterrows():
    out = f"{T}/{r.cik}.txt.gz"
    if os.path.exists(out):
        ok.append(True); continue
    url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.adsh.replace('-', '')}/{r.fn}"
    try:
        html = get(url)
        txt = to_text(html)
        with gzip.open(out, "wt") as f:
            f.write(txt)
        ok.append(True)
    except Exception as ex:  # noqa: BLE001
        print("FAIL", r.cik, url, ex, flush=True)
        ok.append(False)
    if i % 50 == 0:
        print(i, flush=True)
docs["fetched"] = ok
docs.to_csv(f"{D}/docs.csv", index=False)
print(docs.fetched.sum(), "fetched")
