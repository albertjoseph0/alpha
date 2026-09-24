"""Daily adjusted close + volume + split history for all 13D subject tickers (current tickers, from EDGAR
display names) plus SPY and IWM, from yfinance.

Output: data/orch/o01_activist_13d/px_close.parquet (dividend+split adjusted close), px_vol.parquet
        (split-adjusted volume), px_split.parquet (split ratios; yfinance convention 2.0 = 2-for-1,
        0.1 = 1-for-10 reverse). Raw (unadjusted) price at t ~= adj close * prod(split ratios after t);
        it is used only for the price >= $2 investability filter.
Tickers yfinance cannot find are listed in px_missing.txt (survivorship accounting).
Resumable by ticker: each chunk also writes the tickers it attempted (px_chunks/c*.txt); on a re-run only tickers
not yet attempted are downloaded. `s03_prices.py partial` takes tickers from tickers_partial.txt instead of filings.csv.
"""
import sys
import pathlib
import time

import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "orch" / "o01_activist_13d"
CH = D / "px_chunks"


def main():
    CH.mkdir(exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "partial":
        raw = (D / "tickers_partial.txt").read_text().split()
    else:
        raw = pd.read_csv(D / "filings.csv", dtype=str)["ticker"].dropna().tolist()
    tick = sorted({t.replace(".", "-") for t in raw} | {"SPY", "IWM"})
    tried = set()
    for t in CH.glob("c*.txt"):
        tried |= set(t.read_text().split())
    todo = [t for t in tick if t not in tried]
    print("tickers", len(tick), "to download", len(todo), flush=True)
    k0 = len(list(CH.glob("c*.txt")))
    for i in range(0, len(todo), 100):
        out = CH / f"c{k0 + i // 100:05d}.parquet"
        chunk = todo[i:i + 100]
        for attempt in range(3):
            try:
                df = yf.download(chunk, start="2012-06-01", auto_adjust=True, actions=True, progress=False,
                                 threads=True, group_by="column")
                break
            except Exception as e:  # noqa: BLE001
                print("retry", i, e, flush=True); time.sleep(20)
        parts = {}
        for fld, name in (("Close", "close"), ("Volume", "vol"), ("Stock Splits", "split")):
            x = df[fld] if fld in df.columns.get_level_values(0) else pd.DataFrame(index=df.index)
            if isinstance(x, pd.Series):
                x = x.to_frame(chunk[0])
            parts[name] = x
        long = pd.concat({k: v.stack() for k, v in parts.items()}, axis=1)
        long.index.names = ["date", "tk"]
        long = long.dropna(subset=["close"])
        long.reset_index().to_parquet(out)
        out.with_suffix(".txt").write_text("\n".join(chunk))
        print(i, long.reset_index()["tk"].nunique(), flush=True)
        time.sleep(2)
    if len(sys.argv) > 1 and sys.argv[1] == "partial":
        return
    allp = pd.concat([pd.read_parquet(p) for p in sorted(CH.glob("c*.parquet"))])
    close = allp.pivot_table(index="date", columns="tk", values="close", aggfunc="last")
    good = [t for t in close.columns if close[t].notna().sum() > 20]
    close = close[good].sort_index()
    vol = allp.pivot_table(index="date", columns="tk", values="vol", aggfunc="last").reindex(columns=good)
    spl = allp[(allp["split"].fillna(0) != 0) & allp["tk"].isin(good)][["date", "tk", "split"]]
    close.to_parquet(D / "px_close.parquet")
    vol.reindex(close.index).to_parquet(D / "px_vol.parquet")
    spl.to_parquet(D / "px_split.parquet")
    missing = sorted(set(tick) - set(good))
    (D / "px_missing.txt").write_text("\n".join(missing))
    print("tickers", len(tick), "with prices", len(good), "missing", len(missing))


if __name__ == "__main__":
    main()
