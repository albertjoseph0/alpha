"""Re-list every EFTS hit (initial 13Ds AND amendments) from the s01 cache and save them all.

Used only for point-in-time filer-history features (how many 13Ds a filer CIK filed in the prior 365 days).
Run after s01_list.py; every EFTS page is already in the SEC disk cache, so this makes no new requests.
Output: data/orch/o01_activist_13d/all_hits.parquet
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from s01_list import OUT, month_hits  # noqa: E402


def main():
    rows = []
    for m in pd.period_range("2013-01", "2026-08", freq="M"):
        start, end = str(m.start_time.date()), str(m.end_time.date())
        for form in ("SC 13D", "SCHEDULE 13D"):
            if form == "SCHEDULE 13D" and m < pd.Period("2024-12", "M"):
                continue
            rows += month_hits(form, start, end)
    df = pd.DataFrame(rows).drop_duplicates("adsh")
    df.to_parquet(OUT / "all_hits.parquet")
    print(df["form"].value_counts())


if __name__ == "__main__":
    main()
