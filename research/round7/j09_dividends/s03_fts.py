"""EDGAR full-text search (efts) for 8-K documents announcing dividend increases / initiations / specials.
EDGAR FTS has no wildcards or stemming, so 'initiat* quarterly dividend' / 'increase* quarterly dividend' are
expanded into explicit phrase variants joined with OR (verified: OR sums phrase counts).
One query per (phrase group, half-year), paginated 100 hits/page. All filers are returned; the universe filter is
applied later. -> DATA/fts_hits.parquet (one row per hit document). Resumable (sec.get caches every page).
Usage: s03_fts.py [first_year last_year]"""
import json, sys, urllib.parse
import pandas as pd
from common import DATA, get

INC = ["increases quarterly dividend", "increased quarterly dividend", "increase quarterly dividend",
       "increases its quarterly dividend", "increased its quarterly dividend", "increase its quarterly dividend",
       "increase in quarterly dividend", "increase in the quarterly dividend", "increase in its quarterly dividend",
       "increase of the quarterly dividend", "increase the quarterly dividend", "increased the quarterly dividend",
       "increases quarterly cash dividend", "increased its quarterly cash dividend",
       "increase in the quarterly cash dividend", "increase in its quarterly cash dividend",
       "increases its quarterly cash dividend", "increase its quarterly cash dividend",
       "increased quarterly cash dividend", "increase in quarterly cash dividend",
       "raises quarterly dividend", "raised its quarterly dividend", "raises its quarterly dividend",
       "raises quarterly cash dividend", "quarterly dividend increase", "increases dividend", "raises dividend",
       "dividend increase", "increases regular quarterly dividend", "increase in its regular quarterly dividend",
       "increase in the regular quarterly dividend", "increased its regular quarterly dividend",
       "increases annual dividend", "increase in the annual dividend", "increases cash dividend",
       "increase in its quarterly common stock dividend", "increase in the quarterly common stock dividend"]
INI = ["initiates quarterly dividend", "initiates quarterly cash dividend", "initiates a quarterly dividend",
       "initiate a quarterly dividend", "initiated a quarterly dividend", "initiating a quarterly dividend",
       "initiation of a quarterly dividend", "initiation of quarterly dividend", "initiation of a quarterly cash dividend",
       "initiate a quarterly cash dividend", "initiated a quarterly cash dividend", "initiating a quarterly cash dividend",
       "initiates dividend", "initiates cash dividend", "initiate a regular quarterly dividend",
       "initiation of a regular quarterly dividend", "initiates regular quarterly dividend", "dividend initiation",
       "initiation of a dividend", "initiate a dividend", "initiates first quarterly dividend",
       "first quarterly dividend", "first-ever quarterly dividend", "first ever quarterly dividend",
       "inaugural quarterly dividend", "initial quarterly dividend", "inaugural dividend",
       "institutes quarterly dividend", "establishes quarterly dividend", "reinstates quarterly dividend",
       "reinstatement of the quarterly dividend", "reinstatement of its quarterly dividend",
       "reinstate the quarterly dividend", "reinstates dividend", "reinstatement of quarterly dividend",
       "resumption of the quarterly dividend", "resumes quarterly dividend", "reinstated its quarterly dividend"]
SPE = ["special dividend", "special cash dividend", "variable dividend", "variable quarterly dividend",
       "supplemental dividend", "special one-time dividend", "one-time special dividend"]
GROUPS = {"inc": INC, "ini": INI, "spe": SPE}
URL = "https://efts.sec.gov/LATEST/search-index?"


def query(phrases, s, e, frm):
    q = " OR ".join(f'"{p}"' for p in phrases)
    u = URL + urllib.parse.urlencode({"q": q, "forms": "8-K", "dateRange": "custom", "startdt": s, "enddt": e,
                                      "from": frm})
    return json.loads(get(u))


def split(phrases, n=12):  # keep each URL short enough
    return [phrases[i:i + n] for i in range(0, len(phrases), n)]


if __name__ == "__main__":
    y0, y1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2012, 2026)
    out = DATA / "fts_hits.parquet"
    rows = []
    for y in range(y0, y1 + 1):
        for s, e in ((f"{y}-01-01", f"{y}-06-30"), (f"{y}-07-01", f"{y}-12-31")):
            for gname, ph in GROUPS.items():
                for k, chunk in enumerate(split(ph)):
                    frm, tot = 0, None
                    while True:
                        try:
                            j = query(chunk, s, e, frm)
                        except Exception as ex:  # noqa: BLE001
                            print("ERR", gname, k, s, frm, ex, flush=True)
                            break
                        tot = j["hits"]["total"]["value"]
                        hh = j["hits"]["hits"]
                        for h in hh:
                            src = h["_source"]
                            rows.append({"grp": gname, "chunk": k, "adsh": src["adsh"],
                                         "file": h["_id"].split(":", 1)[1], "cik": int(src["ciks"][0]),
                                         "name": (src.get("display_names") or [""])[0],
                                         "file_date": src["file_date"], "file_type": src.get("file_type"),
                                         "items": ",".join(src.get("items") or []), "score": h.get("_score")})
                        frm += len(hh)
                        if not hh or frm >= tot or frm >= 9900:
                            break
                    print(y, s[5:7], gname, k, "total", tot, "rows", len(rows), flush=True)
                    if tot and tot >= 10000:
                        print("WARNING capped", gname, k, s, flush=True)
    d = pd.DataFrame(rows)
    if out.exists() and (y0, y1) != (2012, 2026):
        old = pd.read_parquet(out)
        d = pd.concat([old, d]).drop_duplicates(["grp", "chunk", "adsh", "file"])
    d.to_parquet(out)
    print("hits", len(d), "filings", d.adsh.nunique(), "ciks", d.cik.nunique())
