"""SEC XBRL frames: dei:EntityCommonStockSharesOutstanding for every quarter (cover-page shares
outstanding; available ~2009+). One request per quarter. Used only for market-cap buckets."""
import requests, time, pandas as pd, os
UA = "alpha-research contact@alpha-research.dev"
rows = []
for y in range(2009, 2027):
    for q in range(1, 5):
        u = f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY{y}Q{q}I.json"
        r = requests.get(u, headers={"User-Agent": UA}, timeout=60); time.sleep(1.0)
        if r.status_code != 200:
            print(y, q, r.status_code); continue
        d = r.json()["data"]
        for x in d:
            rows.append((x["cik"], x["end"], x["val"]))
        print(y, q, len(d), flush=True)
df = pd.DataFrame(rows, columns=["cik", "end", "shares"])
df["end"] = pd.to_datetime(df.end)
df.to_parquet("data/round5/m05_insider_clusters/shares_out.parquet", index=False)
