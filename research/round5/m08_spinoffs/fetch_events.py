"""Step 1: pull every Form 10-12B / 10-12G (and amendments) from EDGAR full-index form.gz, 2003Q1..2026Q3.
Stream each quarterly index, keep only the 10-12 lines, write data/round5/m08_spinoffs/form10_filings.csv.
Raw index files are not kept (filtered on the fly)."""
import gzip, io, time, os, sys, re
import requests
import pandas as pd

UA = {"User-Agent": "alpha-research contact@alpha-research.dev"}
D = "/home/user/alpha/data/round5/m08_spinoffs"
CACHE = f"{D}/idx_cache"
os.makedirs(CACHE, exist_ok=True)

rows = []
for y in range(2003, 2027):
    for q in range(1, 5):
        if y == 2026 and q > 3:
            continue
        cf = f"{CACHE}/{y}Q{q}.txt"
        if not os.path.exists(cf):
            url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.gz"
            for attempt in range(4):
                r = requests.get(url, headers=UA, timeout=120)
                if r.status_code == 200:
                    break
                time.sleep(2 + attempt * 3)
            if r.status_code != 200:
                print("FAIL", url, r.status_code); continue
            txt = gzip.decompress(r.content).decode("latin-1")
            keep = [l for l in txt.splitlines() if l.startswith("10-12")]
            open(cf, "w").write("\n".join(keep))
            time.sleep(0.3)
        for l in open(cf).read().splitlines():
            # fixed-width: form(12) company(62) cik(12) date(12) file
            m = re.match(r"^(\S+)\s+(.*?)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$", l)
            form, comp, cik, date, fn = m.groups()
            rows.append((form, comp, int(cik), date, fn))
        print(y, q, len(rows), flush=True)

df = pd.DataFrame(rows, columns=["form", "company", "cik", "date", "file"])
df.to_csv(f"{D}/form10_filings.csv", index=False)
print(df.form.value_counts())
