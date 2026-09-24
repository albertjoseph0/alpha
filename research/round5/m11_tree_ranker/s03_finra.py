"""FINRA Reg SHO daily short-sale volume, summed over reporting facilities (FNSQ, FNYX, FNQC, FORF;
the consolidated CNMS file only exists from 2018-08, so facility files are used throughout for
consistency). Only the LAST 10 trading days of each month are fetched (the feature is the month-end
short-volume ratio over those days). Filtered to the union universe and aggregated per month:
DATA/finra/YYYY-MM.csv (ticker, short, total). Resumable. Files for day d are published the
evening of d, so a month-end-t feature is known before the t+1 close trade."""
import io
import time
import requests
from common import *

U = set(pd.read_csv(DATA / "sp500_membership_monthly.csv").ticker) | \
    set(pd.read_csv(M01 / "membership_monthly.csv").ticker)
U = {t for t in U if "#" not in t}
cal = pd.read_pickle(M01 / "close.pkl")["SPY"].dropna().index
cal = pd.to_datetime(cal)
out = DATA / "finra"
out.mkdir(exist_ok=True)
S = requests.Session()
FAC = ["FNSQ", "FNYX", "FNQC", "FORF"]

for per, days in pd.Series(cal, index=cal).groupby(cal.to_period("M")):
    if per < pd.Period("2011-06") or per > pd.Period("2026-08"):
        continue
    f = out / f"{per}.csv"
    if f.exists():
        continue
    parts = []
    nfiles = 0
    for d in days.iloc[-10:]:
        for fac in FAC:
            url = f"https://cdn.finra.org/equity/regsho/daily/{fac}shvol{d:%Y%m%d}.txt"
            for att in range(3):
                try:
                    r = S.get(url, timeout=30)
                    break
                except Exception as e:
                    print("retry", url, e, flush=True)
                    time.sleep(5)
            else:
                continue
            time.sleep(0.15)
            if r.status_code != 200 or len(r.content) < 200:
                continue
            df = pd.read_csv(io.StringIO(r.text), sep="|", dtype={"Symbol": str})
            df = df[pd.to_numeric(df["Date"], errors="coerce").notna()]
            df["ticker"] = df["Symbol"].astype(str).str.replace(".", "-", regex=False).str.replace("/", "-", regex=False)
            df = df[df.ticker.isin(U)]
            parts.append(df[["ticker", "ShortVolume", "TotalVolume"]])
            nfiles += 1
    if parts:
        a = pd.concat(parts).groupby("ticker")[["ShortVolume", "TotalVolume"]].sum()
        a.columns = ["short", "total"]
        a["nfiles"] = nfiles
        a.to_csv(f)
    print(per, nfiles, len(parts) and len(a), flush=True)
