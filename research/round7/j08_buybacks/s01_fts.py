"""EDGAR full-text search (efts) for buyback-announcement language in 8-K documents (main doc + exhibits).
Usage: python s01_fts.py 2013 2026 [query_keys...]. Pages of 100, split by half-year to stay far below the 10k cap.
Output: DATA/fts/<key>_<year>.parquet (one row per hit document), resumable (sec.get caches every page)."""
import time
from common import *

Q = {
    "auth_new": '"authorized a new" repurchase',
    "appr_new": '"approved a new" repurchase',
    "auth_add": '"authorized an additional" repurchase',
    "appr_add": '"approved an additional" repurchase',
    "new_prog": '"new share repurchase" OR "new stock repurchase" OR "new repurchase program" OR "new buyback"',
    "asr": '"accelerated share repurchase" OR "accelerated stock repurchase"',
    "incr_auth": '"increase" "repurchase authorization"',
    "rep_of": '"authorized the repurchase of" OR "approved the repurchase of"',
    "has_auth": '"has authorized" repurchase',
    "has_appr": '"has approved" repurchase',
    "bod_auth": '"board of directors authorized" repurchase',
    "bod_appr": '"board of directors approved" repurchase',
}
OUT = DATA / "fts"
OUT.mkdir(exist_ok=True)


def run(key, year):
    f = OUT / f"{key}_{year}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    rows = []
    for a, b in [(f"{year}-01-01", f"{year}-06-30"), (f"{year}-07-01", f"{year}-12-31")]:
        frm = 0
        while True:
            d = efts(Q[key], a, b, frm)
            hits = d["hits"]["hits"]
            for h in hits:
                s = h["_source"]
                adsh, fn = h["_id"].split(":", 1)
                rows.append(dict(key=key, adsh=adsh, fn=fn, ciks=",".join(s.get("ciks") or []),
                                 name=(s.get("display_names") or [""])[0], date=s["file_date"],
                                 ftype=s.get("file_type"), items=",".join(s.get("items") or []), form=s.get("form")))
            tot = d["hits"]["total"]["value"]
            frm += len(hits)
            if not hits or frm >= tot or frm >= 9900:
                break
    df = pd.DataFrame(rows, columns=["key", "adsh", "fn", "ciks", "name", "date", "ftype", "items", "form"])
    df.to_parquet(f, index=False)
    return df


if __name__ == "__main__":
    y0, y1 = int(sys.argv[1]), int(sys.argv[2])
    keys = sys.argv[3:] or list(Q)
    for y in range(y0, y1 + 1):
        for k in keys:
            t = time.time()
            df = run(k, y)
            print(y, k, len(df), f"{time.time() - t:.0f}s", flush=True)
