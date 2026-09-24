"""First archive month of every spot symbol (all quote currencies), used to decide whether a new
USDT pair is a genuinely new coin listing or just a new quote pair for a coin already on Binance.
Output: data/round5/m09_crypto_flow/spot_first_month.csv (symbol, first_month, last_month)."""
import os, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from fetch import s3_list, D


def one(sym):
    keys, _ = s3_list(f"data/spot/monthly/klines/{sym}/1d/")
    ms = sorted(k.split("-1d-")[1][:7] for k in keys if k.endswith(".zip"))
    return sym, (ms[0] if ms else ""), (ms[-1] if ms else "")


if __name__ == "__main__":
    lst = f"{D}/spot_symbols.txt"
    if not os.path.exists(lst):
        _, pre = s3_list("data/spot/monthly/klines/")
        open(lst, "w").write("\n".join(p.split("/")[-2] for p in pre))
    syms = open(lst).read().split()
    out = []
    with ThreadPoolExecutor(6) as ex:
        for i, r in enumerate(ex.map(one, syms)):
            out.append(r)
            if i % 200 == 0:
                print(i, flush=True)
    with open(f"{D}/spot_first_month.csv", "w") as f:
        f.write("symbol,first_month,last_month\n")
        for s, a, b in out:
            f.write(f"{s},{a},{b}\n")
