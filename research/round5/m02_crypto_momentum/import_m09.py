"""One-off (5b): reuse identical Binance 1d spot kline files already downloaded by m09 (read-only),
for symbols m02's fetch had not reached. Validates each file; writes atomically into m02 raw/."""
import os, pandas as pd
SRC = "/home/user/alpha/data/round5/m09_crypto_flow/raw_spot"
DST = "/home/user/alpha/data/round5/m02_crypto_momentum/raw"
COLS = ["open_time","open","high","low","close","volume","close_time","quote_volume","trades","tb_base","tb_quote"]
n = bad = 0
for f in sorted(os.listdir(SRC)):
    out = f"{DST}/{f}"
    if os.path.exists(out) or not f.endswith(".csv"): continue
    p = f"{SRC}/{f}"
    if os.path.getsize(p) == 0:
        continue  # ambiguous; let fetch.py decide
    try:
        df = pd.read_csv(p, header=None, dtype=str)
        df = df[pd.to_numeric(df[0], errors="coerce").notna()].iloc[:, :11]
        df.columns = COLS
        assert df.notna().all().all() and len(df) > 0
        pd.to_numeric(df.close_time); pd.to_numeric(df.tb_quote)
    except Exception as e:
        bad += 1; print("skip", f, e); continue
    if os.path.exists(out): continue
    df.to_csv(out + ".tmp", index=False); os.replace(out + ".tmp", out); n += 1
print("imported", n, "bad", bad)
