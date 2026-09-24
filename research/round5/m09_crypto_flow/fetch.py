"""m09 fetch: Binance public archive (data.binance.vision) only.

1. USD-M perpetual funding-rate history for every symbol under futures/um/monthly/fundingRate/
   (includes delisted contracts - the archive keeps them).
2. Spot 1d klines for every *USDT spot pair under spot/monthly/klines/ (includes delisted pairs),
   keeping taker-buy volume columns.
Outputs (aggregated, raw files deleted afterwards):
   data/round5/m09_crypto_flow/funding.parquet  (symbol, calc_time[ms], rate)
   data/round5/m09_crypto_flow/spot_1d.parquet  (symbol, date, o/h/l/c, vol, qvol, trades, tb_base, tb_quote)
"""
import os, io, sys, time, zipfile, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

D = "/home/user/alpha/data/round5/m09_crypto_flow"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BASE = "https://data.binance.vision/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def s3_list(prefix):
    keys, prefixes, marker = [], [], ""
    while True:
        url = f"{S3}?delimiter=/&prefix={prefix}&marker={urllib.parse.quote(marker)}"
        root = ET.fromstring(get(url))
        keys += [c.find("s:Key", NS).text for c in root.findall("s:Contents", NS)]
        prefixes += [p.find("s:Prefix", NS).text for p in root.findall("s:CommonPrefixes", NS)]
        if root.find("s:IsTruncated", NS).text != "true":
            break
        nm = root.find("s:NextMarker", NS)
        marker = nm.text if nm is not None else (keys[-1] if keys else prefixes[-1])
    return keys, prefixes


def read_zip_csv(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    with z.open(z.namelist()[0]) as f:
        return pd.read_csv(f, header=None, dtype=str)


def fetch_symbol(prefix, out):
    if os.path.exists(out):
        return
    keys, _ = s3_list(prefix)
    keys = [k for k in keys if k.endswith(".zip")]
    frames = []
    for k in keys:
        frames.append(read_zip_csv(get(BASE + k)))
        pass
    if frames:
        pd.concat(frames).to_csv(out, index=False, header=False)
    else:
        open(out, "w").close()


def main(which):
    if which == "fund":
        lst = f"{D}/fund_symbols.txt"
        if not os.path.exists(lst):
            _, pre = s3_list("data/futures/um/monthly/fundingRate/")
            open(lst, "w").write("\n".join(p.split("/")[-2] for p in pre))
        syms = open(lst).read().split()
        jobs = [(f"data/futures/um/monthly/fundingRate/{s}/", f"{D}/raw_fund/{s}.csv") for s in syms]
    else:
        lst = f"{D}/spot_symbols.txt"
        if not os.path.exists(lst):
            _, pre = s3_list("data/spot/monthly/klines/")
            open(lst, "w").write("\n".join(p.split("/")[-2] for p in pre))
        syms = [s for s in open(lst).read().split() if s.endswith("USDT")]
        jobs = [(f"data/spot/monthly/klines/{s}/1d/", f"{D}/raw_spot/{s}.csv") for s in syms]
    print(which, len(jobs), "symbols", flush=True)
    with ThreadPoolExecutor(12) as ex:
        for i, _ in enumerate(ex.map(lambda j: fetch_symbol(*j), jobs)):
            if i % 50 == 0:
                print(i, flush=True)


def aggregate():
    rows = []
    for f in sorted(os.listdir(f"{D}/raw_fund")):
        p = f"{D}/raw_fund/{f}"
        if os.path.getsize(p) == 0:
            continue
        df = pd.read_csv(p, header=None, dtype=str)
        df = df[pd.to_numeric(df[0], errors="coerce").notna()]
        # columns: calc_time, funding_interval_hours, last_funding_rate
        out = pd.DataFrame({"symbol": f[:-4], "calc_time": pd.to_numeric(df[0]).astype("int64"),
                            "interval_h": pd.to_numeric(df[1]), "rate": pd.to_numeric(df[2])})
        rows.append(out)
    fund = pd.concat(rows).drop_duplicates(["symbol", "calc_time"]).sort_values(["symbol", "calc_time"])
    fund.to_parquet(f"{D}/funding.parquet", index=False)
    print("funding", fund.shape, fund.symbol.nunique())

    rows = []
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "qvol", "trades", "tb_base", "tb_quote"]
    for f in sorted(os.listdir(f"{D}/raw_spot")):
        p = f"{D}/raw_spot/{f}"
        if os.path.getsize(p) == 0:
            continue
        df = pd.read_csv(p, header=None, dtype=str)
        df = df[pd.to_numeric(df[0], errors="coerce").notna()].iloc[:, :11]
        df.columns = cols
        df = df.apply(pd.to_numeric)
        ot = df.open_time.where(df.open_time < 1e14, df.open_time // 1000)  # 2025+ files in microseconds
        df["date"] = pd.to_datetime(ot, unit="ms").dt.normalize()
        df["symbol"] = f[:-4]
        rows.append(df[["symbol", "date", "open", "high", "low", "close", "volume", "qvol", "trades", "tb_base", "tb_quote"]])
    spot = pd.concat(rows).drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])
    spot.to_parquet(f"{D}/spot_1d.parquet", index=False)
    print("spot", spot.shape, spot.symbol.nunique(), spot.date.min(), spot.date.max())


if __name__ == "__main__":
    if sys.argv[1] == "agg":
        aggregate()
    else:
        main(sys.argv[1])
