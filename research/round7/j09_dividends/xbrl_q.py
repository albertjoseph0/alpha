"""Quarterly dividends-per-share series from XBRL facts.
Per (cik, concept, period) keep the latest-filed value (split basis ~ today, so ratios are consistent), take
3-month facts directly and derive missing quarters from year-to-date differences (Q4 = FY - 9M, etc.).
Declared is preferred; CashPaid is used only for CIKs without Declared facts.
-> DATA/dps_quarterly.parquet [cik, qstart, qend, dps, concept, src]"""
import numpy as np
import pandas as pd
from common import DATA

FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "10-KT"}


def quarters(d):
    d = d[(d.unit == "USD/shares") & d.form.isin(FORMS) & d.start.notna()].copy()
    d["dur"] = (d.end - d.start).dt.days
    d = d.sort_values("filed").drop_duplicates(["cik", "concept", "start", "end"], keep="last")
    out = []
    for (cik, con), g in d.groupby(["cik", "concept"]):
        q = {}
        for r in g[(g.dur >= 75) & (g.dur <= 105)].itertuples():
            q[(r.start, r.end)] = (r.val, "q")
        # YTD chains by fiscal-year start
        for s, h in g[g.dur >= 75].groupby("start"):
            h = h.sort_values("end")
            prev_end, prev_val = None, 0.0
            for r in h.itertuples():
                k = round(r.dur / 91.3)
                if k < 1 or k > 4 or abs(r.dur - 91.3 * k) > 20:
                    continue
                if k == 1:
                    prev_end, prev_val = r.end, r.val
                    continue
                if prev_end is not None and round((prev_end - s).days / 91.3) == k - 1:
                    qs = prev_end + pd.Timedelta(days=1)
                    if not any(abs((a - qs).days) <= 5 and abs((b - r.end).days) <= 5 for a, b in q):
                        q[(qs, r.end)] = (r.val - prev_val, "ytd")
                prev_end, prev_val = r.end, r.val
        for (a, b), (v, src) in q.items():
            out.append((cik, a, b, v, con, src))
    o = pd.DataFrame(out, columns=["cik", "qstart", "qend", "dps", "concept", "src"])
    has_decl = set(o[o.concept.str.endswith("Declared")].cik)
    o = o[o.concept.str.endswith("Declared") | ~o.cik.isin(has_decl)]
    o = o.sort_values(["cik", "qend", "src"]).drop_duplicates(["cik", "qend"])
    o["dps"] = o.dps.round(6).clip(lower=0)
    return o.reset_index(drop=True)


if __name__ == "__main__":
    d = pd.read_parquet(DATA / "dps_facts.parquet")
    q = quarters(d)
    q.to_parquet(DATA / "dps_quarterly.parquet")
    print(len(q), "firm-quarters", q.cik.nunique(), "ciks", q.src.value_counts().to_dict(),
          q.concept.value_counts().to_dict())
    print(q[q.cik == 320193].tail(8).to_string())
    q["y"] = q.qend.dt.year
    print(q.groupby("y").cik.nunique().to_string())
