"""Download Binance public-archive daily spot klines for every *USDT pair (incl. delisted).
Output: data/round5/m02_crypto_momentum/klines_1d.parquet (long format)."""
import os, io, re, time, zipfile, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

D = "/home/user/alpha/data/round5/m02_crypto_momentum"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BASE = "https://data.binance.vision/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}

def get(url, tries=8):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(1)

def s3_list(prefix, delimiter="/"):
    keys, prefixes, marker = [], [], ""
    while True:
        url = f"{S3}?delimiter={delimiter}&prefix={urllib.parse.quote(prefix)}&marker={urllib.parse.quote(marker)}"
        root = ET.fromstring(get(url))
        for c in root.findall("s:Contents", NS): keys.append(c.find("s:Key", NS).text)
        for p in root.findall("s:CommonPrefixes", NS): prefixes.append(p.find("s:Prefix", NS).text)
        if root.find("s:IsTruncated", NS).text != "true": break
        nm = root.find("s:NextMarker", NS)
        marker = nm.text if nm is not None else (keys[-1] if keys else prefixes[-1])
    return keys, prefixes

import urllib.parse
def main():
    symfile = f"{D}/symbols_all.txt"
    if not os.path.exists(symfile):
        _, pre = s3_list("data/spot/monthly/klines/")
        syms = [p.split("/")[-2] for p in pre]
        open(symfile, "w").write("\n".join(syms))
    syms = open(symfile).read().split()
    usdt = [s for s in syms if s.endswith("USDT")]
    print(len(syms), "symbols;", len(usdt), "USDT pairs", flush=True)

    def one(sym):
        out = f"{D}/raw/{sym}.csv"
        if os.path.exists(out): return sym, "cached"
        keys, _ = s3_list(f"data/spot/monthly/klines/{sym}/1d/")
        keys = [k for k in keys if k.endswith(".zip")]
        def dl(k):
            z = zipfile.ZipFile(io.BytesIO(get(BASE + urllib.parse.quote(k))))
            with z.open(z.namelist()[0]) as f:
                return pd.read_csv(f, header=None)
        with ThreadPoolExecutor(4) as inner:
            frames = list(inner.map(dl, keys))
        if not frames:
            open(out, "w").write(""); return sym, 0
        df = pd.concat(frames)
        # drop header rows if any
        df = df[pd.to_numeric(df[0], errors="coerce").notna()].iloc[:, :11]
        df.columns = ["open_time","open","high","low","close","volume","close_time","quote_volume","trades","tb_base","tb_quote"]
        df.to_csv(out, index=False)
        return sym, len(keys)

    with ThreadPoolExecutor(4) as ex:
        for i, (s, n) in enumerate(ex.map(one, usdt)):
            if i % 50 == 0: print(i, s, n, flush=True)

    rows = []
    for s in usdt:
        p = f"{D}/raw/{s}.csv"
        if os.path.getsize(p) == 0: continue
        df = pd.read_csv(p)
        ot = pd.to_numeric(df.open_time)
        ot = ot.where(ot < 1e14, ot // 1000)  # 2025+ files are in microseconds
        df["date"] = pd.to_datetime(ot, unit="ms").dt.normalize()
        df["symbol"] = s
        rows.append(df[["symbol","date","open","high","low","close","volume","quote_volume","trades"]])
    allk = pd.concat(rows).drop_duplicates(["symbol","date"]).sort_values(["symbol","date"])
    allk.to_parquet(f"{D}/klines_1d.parquet", index=False)
    print(allk.shape, allk.date.min(), allk.date.max())

if __name__ == "__main__":
    main()
