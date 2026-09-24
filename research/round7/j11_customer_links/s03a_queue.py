"""Build / extend the 10-K fetch queue.

Filter: universe CIKs whose SIC is in industries that sell to identifiable corporate customers (manufacturing,
energy/mining, wholesale, trucking/logistics, business services & software; financials, REITs, utilities,
retail, restaurants, health services, construction are skipped).  Only 10-Ks filed while the ticker was a
member (or in the 12 months before joining) between 2012-01 and 2026-09.

  python s03a_queue.py stage1   -> per CIK: the earliest DEV-era 10-K and the 10-K closest to 2021-09
  python s03a_queue.py stage2   -> all remaining in-window 10-Ks of CIKs whose stage-1 docs contain at least one
                                   candidate name that maps to another universe company (regex screen)
"""
import json
import sys
from common import *

KEEP_SIC = [(1000, 1499), (2000, 3999), (4200, 4299), (4700, 4799), (5000, 5199), (7300, 7399)]


def keep_sic(s):
    try:
        s = int(s)
    except Exception:
        return False
    return any(a <= s <= b for a, b in KEEP_SIC)


def in_window():
    F = pd.read_csv(DATA / "filings_all.csv", parse_dates=["filing_date"])
    F = F[F.form.isin(["10-K", "10-KT"])].drop_duplicates("acc")
    meta = pd.read_csv(DATA / "cik_meta.csv").drop_duplicates("cik")
    U = pd.read_csv(DATA / "universe.csv", parse_dates=["first_me", "last_me"]).dropna(subset=["cik"])
    U["cik"] = U.cik.astype(int)
    w = U.groupby("cik").agg(first_me=("first_me", "min"), last_me=("last_me", "max")).reset_index()
    w = w.merge(meta[["cik", "sic"]], on="cik")
    w = w[w.sic.map(keep_sic)]
    F = F.merge(w, on="cik")
    lo = np.maximum(F.first_me - pd.DateOffset(months=12), pd.Timestamp("2012-01-01"))
    hi = F.last_me + pd.DateOffset(months=1)
    F = F[(F.filing_date >= lo) & (F.filing_date <= hi)]
    return F, w


def write_queue(new):
    qf = DATA / "fetch_queue.csv"
    cols = ["acc", "cik", "primary", "filing_date", "report_date", "accept", "stage", "prio"]
    new = new[cols]
    if qf.exists():
        Q = pd.read_csv(qf)
        new = new[~new.acc.isin(Q.acc)]
        Q = pd.concat([Q, new])
    else:
        Q = new
    Q.to_csv(qf, index=False)
    print("added", len(new), "queue", len(Q), Q.groupby("stage").size().to_dict())


if __name__ == "__main__":
    F, w = in_window()
    print("CIKs kept by SIC:", len(w), "in-window 10-Ks:", len(F), "CIKs with filings:", F.cik.nunique())
    if sys.argv[1] == "stage1":
        rows = []
        for c, g in F.groupby("cik"):
            g = g.sort_values("filing_date")
            a = g[g.filing_date <= "2019-12-31"]
            if len(a):
                rows.append(a.iloc[0])
            b = g[g.filing_date >= "2020-01-01"]
            if len(b):
                rows.append(b.iloc[(b.filing_date - pd.Timestamp("2021-09-01")).abs().argmin()])
        S = pd.DataFrame(rows)
        S["stage"], S["prio"] = 1, 1
        write_queue(S)
    elif sys.argv[1] == "stage2":
        from names import Matcher, build_common, accept
        from extract import candidate_names
        common = build_common()
        U = pd.read_csv(DATA / "universe.csv").dropna(subset=["cik"])
        ucik = set(U.cik.astype(int))
        m = Matcher(prefer=ucik)
        hit = set()
        for line in open(DATA / "cands.jsonl"):
            r = json.loads(line)
            if r.get("stage") != 1:
                continue
            for s, _ in r["sents"]:
                for n in candidate_names(s):
                    if not accept(n, common):
                        continue
                    c, how = m.match(n)
                    if c is not None and c in ucik and c != r["cik"]:
                        hit.add(r["cik"])
        print("stage-1 CIKs with a mapped candidate:", len(hit))
        S = F[F.cik.isin(hit)].copy()
        S["stage"] = 2
        S["prio"] = 2 + (S.filing_date.dt.year % 2)      # even filing years first (biennial coverage), then odd
        write_queue(S)
