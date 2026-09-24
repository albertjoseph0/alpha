"""Company-name index for mapping candidate customer names to tickers (code only, no Jev).

Sources: insider-transaction data sets (m05; issuer CIK, name and trading symbol as reported in each year, so
historical/delisted names are included), SEC company_tickers.json (current), and our universe's EDGAR names and
former names.  Matching: normalised full-name equality, or the candidate equals the leading tokens of exactly one
indexed name (distinctive first token required)."""
import json
import re
from common import *

SUFFIX = set("""inc incorporated corp corporation co company companies ltd limited llc lp l p plc holdings holding
group sa s a ag nv n v se de del the trust bancorp international intl and its affiliates subsidiaries
""".split())
COMMON_FIRST = set("""american general united national first international global new great north south east west
central pacific atlantic us u s standard advanced applied universal federal texas southern northern western eastern
premier royal southwest northwest midwest continental consolidated allied pioneer liberty capital world health
medical energy power data home best star sun city west""".split())


def norm(name: str) -> str:
    s = str(name).lower()
    s = re.sub(r"/[a-z]{2,3}/?", " ", s)            # EDGAR state suffix '/de/'
    s = s.replace("&", " and ").replace("'s", "s").replace("'", "")
    s = re.sub(r"[\.,\(\)\"]", " ", s)
    s = s.replace("-", " ")
    toks = [t for t in s.split() if t]
    while toks and toks[-1] in SUFFIX:
        toks = toks[:-1]
    while toks and toks[0] == "the":
        toks = toks[1:]
    # drop trailing 'and its affiliates' style tails anywhere
    out = []
    for t in toks:
        if t in {"inc", "corp", "corporation", "ltd", "llc", "plc", "co"} and out:
            break
        out.append(t)
    return " ".join(out)


def build_index():
    """DataFrame(key, joined, cik, year0, year1, name, src) of normalised entity names."""
    f = DATA / "name_index.parquet"
    if f.exists():
        return pd.read_parquet(f)
    rows = []
    for q in sorted((M05 / "quarters").glob("20*q?.parquet")):
        y = int(q.name[:4])
        if y < 2011:
            continue
        d = pd.read_parquet(q, columns=["issuercik", "issuername", "issuertradingsymbol"]).drop_duplicates()
        d["year"] = y
        rows.append(d)
    ins = pd.concat(rows).dropna(subset=["issuername"])
    ins["cik"] = ins.issuercik.astype(int)
    ins["sym"] = ins.issuertradingsymbol.map(norm_ticker)
    a = ins.groupby(["cik", "issuername"]).year.agg(["min", "max"]).reset_index()
    a.columns = ["cik", "name", "year0", "year1"]
    a["src"] = "insider"
    cur = json.load(open(M05 / "company_tickers.json"))
    b = pd.DataFrame([(int(v["cik_str"]), v["title"]) for v in cur.values()], columns=["cik", "name"])
    b["year0"], b["year1"], b["src"] = 2026, 2026, "current"
    meta = pd.read_csv(DATA / "cik_meta.csv")
    c = [(r.cik, r.name) for r in meta.itertuples()]
    for r in meta.itertuples():
        if isinstance(r.former, str):
            c += [(r.cik, x) for x in r.former.split("|") if x]
    c = pd.DataFrame(c, columns=["cik", "name"])
    c["year0"], c["year1"], c["src"] = 2011, 2026, "edgar"
    idx = pd.concat([a, b, c], ignore_index=True)
    idx["key"] = idx.name.map(norm)
    idx = idx[idx.key.str.len() > 1]
    idx["joined"] = idx.key.str.replace(" ", "", regex=False)
    idx = idx.groupby(["key", "joined", "cik"]).agg(year0=("year0", "min"), year1=("year1", "max"),
                                                    name=("name", "first")).reset_index()
    idx.to_parquet(f)
    # ticker per (cik, year) from the insider data (mode), plus current tickers
    s = ins.dropna(subset=["sym"]).groupby(["cik", "year", "sym"]).size().reset_index(name="n")
    s = s.sort_values("n").drop_duplicates(["cik", "year"], keep="last")[["cik", "year", "sym"]]
    b2 = pd.DataFrame([(int(v["cik_str"]), norm_ticker(v["ticker"])) for v in cur.values()], columns=["cik", "sym"])
    b2 = b2.drop_duplicates("cik")
    b2["year"] = 2026
    pd.concat([s, b2]).drop_duplicates(["cik", "year"]).to_parquet(DATA / "cik_year_sym.parquet")
    return idx


class Matcher:
    def __init__(self, prefer=None):
        self.prefer = set(prefer) if prefer is not None else None
        idx = build_index()
        self.by_key = idx.groupby("key").cik.apply(lambda x: sorted(set(x))).to_dict()
        self.by_joined = idx.groupby("joined").cik.apply(lambda x: sorted(set(x))).to_dict()
        self.keys = idx[["key", "cik"]].drop_duplicates()
        self.first = {}
        for k, c in zip(self.keys.key, self.keys.cik):
            self.first.setdefault(k.split()[0], []).append((k, c))

    def match(self, cand: str):
        """-> (cik or None, how)."""
        k = norm(cand)
        if not k or len(k) < 3:
            return None, "short"
        for dic, key, how in ((self.by_key, k, "exact"), (self.by_joined, k.replace(" ", ""), "joined")):
            cs = dic.get(key)
            if cs:
                if len(cs) > 1 and self.prefer is not None:
                    cs = [c for c in cs if c in self.prefer] or cs
                return (cs[0], how) if len(cs) == 1 else (None, "ambiguous")
        toks = k.split()
        if toks[0] in COMMON_FIRST and len(toks) < 2:
            return None, "common"
        pool = self.first.get(toks[0], [])
        hits = {c for kk, c in pool if kk.split()[:len(toks)] == toks}
        if len(hits) > 1 and self.prefer is not None:
            hits = {c for c in hits if c in self.prefer} or hits
        if len(hits) == 1:
            return hits.pop(), "prefix"
        if len(hits) > 1:
            return None, "ambiguous"
        return None, "none"


CORP_SUFFIX = re.compile(r"(?i)\b(inc|incorporated|corp|corporation|company|co|ltd|limited|llc|plc|stores|"
                         r"holdings|group|n\.?v|s\.?a|ag)\b\.?")


def build_common(min_count: int = 3):
    """Lower-case word frequencies in the candidate sentences (+ any extra texts): a single-token name that is also
    an ordinary lower-case word ('Trade', 'Joint', 'Target') is accepted only with a corporate suffix."""
    import collections
    import json
    cnt = collections.Counter()
    for line in open(DATA / "cands.jsonl"):
        for s, _ in json.loads(line)["sents"]:
            cnt.update(re.findall(r"(?<![A-Za-z])([a-z][a-z\-']{2,})(?![A-Za-z])", s))
    words = sorted(w for w, n in cnt.items() if n >= min_count)
    (DATA / "common_words.txt").write_text("\n".join(words))
    return set(words)


def load_common():
    f = DATA / "common_words.txt"
    return set(f.read_text().split()) if f.exists() else build_common()


def accept(surface: str, common: set) -> bool:
    k = norm(surface)
    if len(k.split()) == 1 and k.replace(" ", "") in common and not CORP_SUFFIX.search(surface):
        return False
    return True
