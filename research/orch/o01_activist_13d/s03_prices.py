"""Daily adjusted close + volume for all 13D subject tickers (current tickers, from EDGAR display names)
plus SPY and IWM, from yfinance. Output: data/orch/o01_activist_13d/px_close.parquet, px_vol.parquet.
Tickers yfinance cannot find are listed in px_missing.txt (survivorship accounting)."""
import pathlib

import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "orch" / "o01_activist_13d"


def main():
    f = pd.read_csv(D / "filings.csv", dtype=str)
    tick = sorted(set(f["ticker"].dropna().str.replace(".", "-", regex=False)) | {"SPY", "IWM"})
    closes, vols, missing = [], [], []
    for i in range(0, len(tick), 150):
        chunk = tick[i:i + 150]
        df = yf.download(chunk, start="2012-06-01", auto_adjust=True, progress=False, threads=True)
        c, v = df["Close"], df["Volume"]
        if isinstance(c, pd.Series):
            c, v = c.to_frame(chunk[0]), v.to_frame(chunk[0])
        good = [t for t in chunk if t in c and c[t].notna().sum() > 20]
        missing += [t for t in chunk if t not in good]
        closes.append(c[good]); vols.append(v[good])
        print(i, len(good), flush=True)
    pd.concat(closes, axis=1).to_parquet(D / "px_close.parquet")
    pd.concat(vols, axis=1).to_parquet(D / "px_vol.parquet")
    (D / "px_missing.txt").write_text("\n".join(missing))
    print("tickers", len(tick), "missing", len(missing))


if __name__ == "__main__":
    main()
