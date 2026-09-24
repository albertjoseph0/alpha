"""For each text formation (end of April of TEXT_YEARS), fetch the latest 10-K of every priced universe member
(accepted <= formation date, filed since Jan of the prior year), extract Item 1 (truncated) + competition passages.
Raw HTML is never stored (sec.get cache=False). Output: DATA/docs/F<year>.jsonl.gz (one record per firm).
Resumable and time-boxed: usage  python s03_docs.py <years comma-separated> [max_minutes]"""
import gzip
import json
import sys
import time
from common import *
from sec import get
from extract import html_to_text, item1, competition_text

TEXT_YEARS = [2012, 2015, 2018, 2021, 2024]
DD = DATA / "docs"
DD.mkdir(exist_ok=True)


def load_docs(y):
    f = DD / f"F{y}.jsonl.gz"
    recs = []
    if not f.exists():
        return recs
    try:
        with gzip.open(f, "rt") as fh:
            for ln in fh:
                try:
                    recs.append(json.loads(ln))
                except Exception:
                    pass
    except (EOFError, OSError):
        pass
    return recs


def plan(y):
    U = pd.read_parquet(DATA / "universe_monthly.parquet")
    fdate = pd.Timestamp(f"{y}-{FORM_MONTH:02d}-01") + pd.offsets.MonthEnd(0)
    u = U[(U.month_end == fdate) & U.has_px].dropna(subset=["cik"]).copy()
    u["cik"] = u.cik.astype(int)
    S = pd.read_csv(DATA / "subm_rows.csv").drop_duplicates("acc")
    S["acc_et"] = pd.to_datetime(S.accept, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    S = S[(S.acc_et <= fdate + pd.Timedelta(hours=23, minutes=59)) & (S.filing_date >= f"{y - 1}-01-01")]
    S = S[S.form.isin(["10-K", "10-K405", "10-KT"])].sort_values("acc_et").groupby("cik").tail(1)
    P = u.merge(S, on="cik", how="left")
    return P


def main():
    years = [int(x) for x in sys.argv[1].split(",")]
    max_min = float(sys.argv[2]) if len(sys.argv) > 2 else 18.0
    t0 = time.time()
    for y in years:
        P = plan(y)
        have = {r["cik"] for r in load_docs(y)}
        todo = P[~P.cik.isin(have)]
        print(f"F{y}: members {len(P)}, with 10-K {P.acc.notna().sum()}, stored {len(have)}, todo {len(todo)}", flush=True)
        n = 0
        for r in todo.itertuples():
            if time.time() - t0 > max_min * 60:
                print("time box reached", flush=True)
                return
            rec = {"cik": int(r.cik), "fy": y, "ticker": r.ticker, "idx": int(r.idx)}
            if isinstance(r.acc, str):
                url = f"https://www.sec.gov/Archives/edgar/data/{r.cik}/{r.acc.replace('-', '')}/{r.primary}"
                try:
                    h = get(url, cache=False)
                    txt = html_to_text(h)
                    del h
                    it, meth = item1(txt)
                    rec.update(acc=r.acc, form=r.form, accept=r.accept, filing_date=r.filing_date,
                               report_date=r.report_date, method=meth, n_text=len(txt), n_item1=len(it),
                               item1=it[:30000], comp=competition_text(it))
                except Exception as e:
                    print("fail", r.cik, r.acc, repr(e)[:200], flush=True)
                    if "404" not in repr(e):
                        continue          # transient: retry next run
                    rec.update(acc=r.acc, method="http404")
            else:
                rec.update(method="no10k")
            with gzip.open(DD / f"F{y}.jsonl.gz", "at", compresslevel=6) as fh:
                fh.write(json.dumps(rec) + "\n")
            n += 1
            if n % 50 == 0:
                print(f"F{y} {n}/{len(todo)} {round(time.time() - t0)}s", flush=True)
        print(f"F{y} complete", flush=True)
    (DATA / f"s03_done_{'_'.join(map(str, years))}").write_text("ok")


if __name__ == "__main__":
    main()
