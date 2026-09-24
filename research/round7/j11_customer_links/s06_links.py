"""Regex links and Jev states.

For each fetched 10-K: candidate names (extract.candidate_names, re-run on the stored sentences) -> accepted by the
common-word rule -> matched to a CIK (names.Matcher, preferring universe CIKs).  A *regex link* is a match to
another universe company (with prices).  The Jev state is the de-duplicated candidate sentences that mention a
linked company, with every linked company replaced by a placeholder [C1], [C2], ..., the filer itself replaced by
'the Company', and years replaced by labels relative to the report's fiscal year.
Output: DATA/links_regex.parquet, DATA/jev_states.jsonl"""
import json
import re
from common import *
from extract import candidate_names
from names import Matcher, load_common, accept, norm

MAX_ENT, MAX_SENT, MAX_CHARS = 8, 10, 3500
YEAR_LABEL = {0: "[current fiscal year]", 1: "[prior fiscal year]", 2: "[two years prior]", -1: "[next fiscal year]"}


def relabel_years(s, fy):
    def f(m):
        d = fy - int(m.group(0))
        return YEAR_LABEL.get(d, "[earlier year]" if d > 0 else "[later year]")
    return re.sub(r"\b(?:19[89]\d|20[0-3]\d)\b", f, s)


def sub_forms(s, forms, token):
    for fm in sorted(forms, key=len, reverse=True):
        s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(fm) + r"(?:'s)?(?![A-Za-z0-9])", token, s)
    return s


def main():
    U = pd.read_csv(DATA / "universe.csv").dropna(subset=["cik"])
    U["cik"] = U.cik.astype(int)
    ucik = set(U.cik)
    m = Matcher(prefer=ucik)
    common = load_common()
    Q = pd.read_csv(DATA / "fetch_queue.csv").drop_duplicates("acc").set_index("acc")
    meta = pd.read_csv(DATA / "cik_meta.csv").drop_duplicates("cik").set_index("cik")
    links, states = [], []
    cache = {}
    for line in open(DATA / "cands.jsonl"):
        r = json.loads(line)
        acc, sc = r["acc"], r["cik"]
        if acc not in Q.index:
            continue
        fy = int(str(Q.loc[acc, "report_date"])[:4]) if isinstance(Q.loc[acc, "report_date"], str) else \
            int(str(Q.loc[acc, "filing_date"])[:4]) - 1
        ent, selff = {}, set()
        sent_ents = []
        for s, _ in r["sents"]:
            here = set()
            for n in candidate_names(s):
                if not accept(n, common):
                    continue
                if n not in cache:
                    cache[n] = m.match(n)[0]
                c = cache[n]
                if c is None:
                    continue
                if c == sc:
                    selff.add(n)
                elif c in ucik:
                    ent.setdefault(c, {"forms": set(), "n": 0})
                    ent[c]["forms"].add(n)
                    ent[c]["n"] += 1
                    here.add(c)
            sent_ents.append(here)
        if not ent:
            continue
        top = sorted(ent, key=lambda c: -ent[c]["n"])[:MAX_ENT]
        slot = {c: i + 1 for i, c in enumerate(top)}
        # the filer's own name forms: matched self forms + distinctive leading token of its EDGAR name
        nm = norm(meta.name.get(sc, "")) if sc in meta.index else ""
        if nm and len(nm.split()[0]) >= 4 and nm.split()[0] not in common:
            selff.add(nm.split()[0].capitalize())
            selff.add(nm.split()[0].upper())
        out, seen, nchar = [], set(), 0
        for (s, _), here in zip(r["sents"], sent_ents):
            if not (here & set(top)):
                continue
            k = re.sub(r"\W+", "", s.lower())[:150]
            if k in seen:
                continue
            seen.add(k)
            t = s
            for c in top:
                t = sub_forms(t, ent[c]["forms"], f"[C{slot[c]}]")
            t = sub_forms(t, selff, "the Company")
            t = relabel_years(t, fy)
            if nchar + len(t) > MAX_CHARS and out:
                break
            out.append(t)
            nchar += len(t)
            if len(out) >= MAX_SENT:
                break
        # an entity may have been dropped by the caps: keep only slots that occur in the state
        text = "\n".join(f"- {t}" for t in out)
        present = [c for c in top if f"[C{slot[c]}]" in text]
        for c in top:
            links.append((acc, sc, c, slot[c], "|".join(sorted(ent[c]["forms"])), ent[c]["n"], c in present))
        states.append({"acc": acc, "cik": sc, "slots": {f"C{slot[c]}": int(c) for c in present}, "text": text})
    L = pd.DataFrame(links, columns=["acc", "supplier_cik", "cust_cik", "slot", "forms", "n_mentions", "in_state"])
    L.to_parquet(DATA / "links_regex.parquet")
    with open(DATA / "jev_states.jsonl", "w") as f:
        for s in states:
            f.write(json.dumps(s) + "\n")
    print("docs:", sum(1 for _ in open(DATA / "cands.jsonl")), "docs with regex links:", L.acc.nunique(),
          "links:", len(L), "suppliers:", L.supplier_cik.nunique(), "customers:", L.cust_cik.nunique())
    c2t = dict(zip(U.cik, U.ticker))
    print(L.cust_cik.map(c2t).value_counts().head(25).to_dict())


if __name__ == "__main__":
    main()
