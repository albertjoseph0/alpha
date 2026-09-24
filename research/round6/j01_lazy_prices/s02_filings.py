"""List every 10-K / 10-Q of each universe CIK from EDGAR submissions JSON (via the shared sec.get).
Keep filings made while the ticker (with that CIK in that year) was an S&P 500 member at the prior month-end.
Output: DATA/filings.csv (one row per filing, incl. acceptance time and primary document)."""
import json
import time
from common import *
from sec import get

TY = pd.read_csv(DATA / "ticker_year_cik.csv")
ciks = sorted(TY.cik.unique())
KEEP = {"10-K", "10-K405", "10-Q", "10-KT"}
raw_f = DATA / "submissions_rows.csv"
done = set()
if raw_f.exists():
    done = set(pd.read_csv(raw_f, usecols=["cik"]).cik.unique())
t0 = time.time()
for i, c in enumerate(ciks):
    if c in done:
        continue
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
    except Exception as e:
        print("fail", c, e, flush=True)
        continue
    blocks = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        if f.get("filingTo", "9999") >= "2012-06-01":
            try:
                blocks.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
            except Exception as e:
                print("fail page", c, f["name"], e, flush=True)
    rows = []
    for b in blocks:
        n = len(b["accessionNumber"])
        for k in range(n):
            if b["form"][k] in KEEP and b["filingDate"][k] >= "2012-06-01":
                rows.append((c, j.get("name"), b["form"][k], b["accessionNumber"][k], b["filingDate"][k],
                             b["reportDate"][k], b["acceptanceDateTime"][k], b["primaryDocument"][k],
                             b.get("size", [None] * n)[k]))
    if not rows:
        rows.append((c, j.get("name"), None, None, None, None, None, None, None))
    df = pd.DataFrame(rows, columns=["cik", "name", "form", "acc", "filing_date", "report_date", "accept",
                                     "primary", "size"])
    df.to_csv(raw_f, mode="a", header=not raw_f.exists(), index=False)
    if i % 50 == 0:
        print(i, c, j.get("name"), len(rows), round(time.time() - t0), flush=True)

# membership filter: ticker whose CIK in the filing year maps to this cik, and was a member at the prior month-end
S = pd.read_csv(raw_f).dropna(subset=["acc"]).drop_duplicates("acc")
S["filing_date"] = pd.to_datetime(S.filing_date)
M = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"])
M["base"] = M.ticker.str.split("#").str[0]
M["year"] = M.month_end.dt.year
M = M.merge(TY, left_on=["base", "year"], right_on=["ticker", "year"], suffixes=("", "_ty"))
S["prev_me"] = (S.filing_date - pd.offsets.MonthEnd(1)).dt.normalize()
S["prev_me"] = S.apply(lambda r: r.filing_date.normalize() if r.filing_date.is_month_end else r.prev_me, axis=1)
S["prev_me"] = S.filing_date.dt.to_period("M").dt.to_timestamp() - pd.Timedelta(days=1)
F = S.merge(M[["month_end", "base", "cik"]], left_on=["prev_me", "cik"], right_on=["month_end", "cik"])
F = F.rename(columns={"base": "ticker"}).drop(columns=["month_end"]).drop_duplicates("acc")
F.to_csv(DATA / "filings.csv", index=False)
print("all 10-K/Q rows:", len(S), "member filings:", len(F))
print(F.groupby([F.filing_date.dt.year, "form"]).size().unstack().to_string())
