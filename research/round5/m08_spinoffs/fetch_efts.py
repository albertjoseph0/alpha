"""Step 2: EDGAR full-text search (efts.sec.gov) for spin-off language inside Form 10-12B/10-12G filings.
Collects every matching document (cik, accession, filename, type, date). Cached as JSON pages."""
import json, os, time, hashlib
import requests
import pandas as pd

UA = {"User-Agent": "alpha-research contact@alpha-research.dev"}
D = "/home/user/alpha/data/round5/m08_spinoffs"
C = f"{D}/efts_cache"
os.makedirs(C, exist_ok=True)

QUERIES = ['"spin-off"', '"spinoff"', '"spun off"', '"pro rata distribution"', '"regular-way"', '"when-issued"']
rows = []
for q in QUERIES:
    for form in ["10-12B", "10-12G"]:
        # split by date to stay far below the 10k paging cap
        for (a, b) in [("2003-01-01", "2008-12-31"), ("2009-01-01", "2014-12-31"), ("2015-01-01", "2020-12-31"), ("2021-01-01", "2026-12-31")]:
            frm = 0
            while True:
                key = hashlib.md5(f"{q}|{form}|{a}|{frm}".encode()).hexdigest()
                cf = f"{C}/{key}.json"
                if os.path.exists(cf):
                    d = json.load(open(cf))
                else:
                    params = dict(q=q, forms=form, dateRange="custom", startdt=a, enddt=b)
                    if frm:
                        params["from"] = frm
                    for att in range(5):
                        try:
                            r = requests.get("https://efts.sec.gov/LATEST/search-index", params=params, headers=UA, timeout=60)
                            if r.status_code == 200:
                                break
                        except Exception as e:
                            print("err", e)
                        time.sleep(2 + 3 * att)
                    d = r.json()
                    json.dump(d, open(cf, "w"))
                    time.sleep(0.25)
                hits = d["hits"]["hits"]
                for h in hits:
                    s = h["_source"]
                    adsh, fn = h["_id"].split(":", 1)
                    for cik in s["ciks"]:
                        rows.append(dict(query=q, cik=int(cik), name=s["display_names"][0] if s["display_names"] else "",
                                         adsh=adsh, fn=fn, form=s["form"], root=",".join(s.get("root_forms") or []),
                                         ftype=s.get("file_type"), fdesc=s.get("file_description"), date=s["file_date"]))
                tot = d["hits"]["total"]["value"]
                frm += len(hits)
                if not hits or frm >= tot or frm >= 9900:
                    break
            print(q, form, a, tot, len(rows), flush=True)

df = pd.DataFrame(rows).drop_duplicates()
df.to_csv(f"{D}/efts_hits.csv", index=False)
print(df.cik.nunique(), "ciks")
