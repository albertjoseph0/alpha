"""Step 2: regex metadata + anonymised section windows for every fetched information statement.
Outputs data/round6/j04_spinoffs/meta.csv and sections/<cik>.json (anonymised windows per topic)."""
import json, os, re, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from extract import (D, load, tickers, ratio, shares_out, is_spinoff_doc, parent_name, name_word, aliases,
                     anonymise, sections)

os.makedirs(f"{D}/sections", exist_ok=True)
docs = pd.read_csv(f"{D}/docs.csv") if os.path.exists(f"{D}/docs.csv") else None
if docs is None:  # fetch still running: build from files present
    import importlib.util
    raise SystemExit("docs.csv missing: run 01_fetch_docs.py first")

PARENT_SYM = re.compile(r"\((?:NYSE|NASDAQ|Nasdaq|AMEX|NYSE American|NYSE MKT)[A-Za-z ]{0,12}: ?([A-Z]{1,5}(?:\.[A-Z])?)\)")
rows = []
for _, r in docs[docs.fetched].iterrows():
    fl = load(r.cik)
    nw = name_word(r["name"])
    st, se, pt, pe, nspin = tickers(fl, nw)
    if pt is None:
        m = [x for x in PARENT_SYM.findall(fl) if x != st]
        pt = max(set(m), key=m.count) if m else None
    rt, nrt = ratio(fl)
    pn = parent_name(fl, nw)
    spin = is_spinoff_doc(fl)
    row = dict(cik=r.cik, name=r["name"], doc_date=r.doc_date, first_form10=r.first_form10, root=r.root,
               is_spin_doc=spin, spin_ticker=st, spin_exch=se, parent_ticker=pt, parent_exch=pe, ratio=rt,
               n_ratio=nrt, shares_doc=shares_out(fl), parent_name=pn, name_word=nw, doc_chars=len(fl))
    if spin and (se in ("NYSE", "NASDAQ", "AMEX") or se is None):
        sp, pa = aliases(fl, nw, pn, [st, pt])
        an = anonymise(fl, sp, pa, [st, pt])
        sec = sections(an)
        row["sec_chars"] = sum(len(w) for v in sec.values() for w in v)
        json.dump(sec, open(f"{D}/sections/{r.cik}.json", "w"))
    rows.append(row)
meta = pd.DataFrame(rows)
meta.to_csv(f"{D}/meta.csv", index=False)
print(len(meta), "docs;", meta.is_spin_doc.sum(), "spin docs;",
      (meta.is_spin_doc & meta.spin_exch.isin(["NYSE", "NASDAQ", "AMEX"])).sum(), "exchange-listed spin docs")
print(meta.spin_exch.value_counts(dropna=False))
