"""Shared helpers for j09 (dividend initiations / increases read by Jev). Paths, periods, universe, prices."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/home/user/alpha")
RES = ROOT / "research/round7/j09_dividends"
DATA = ROOT / "data/round7/j09_dividends"
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "research/round5"))
from sec import get  # noqa: E402  shared, rate-limited EDGAR fetcher (never call sec.gov any other way)

AGENT = "j09"
DEV = ("2013-01-01", "2019-12-31")
TEST = ("2020-01-01", "2026-12-31")
M11 = ROOT / "data/round5/m11_tree_ranker"
M01 = ROOT / "data/round5/m01_midcap_momentum"
M06 = ROOT / "data/round5/m06_filing_reader"


def membership():
    """Point-in-time monthly membership: S&P 500 (m11, rebuilt from Wikipedia changes) + S&P 400 (m01)."""
    a = pd.read_csv(M11 / "sp500_membership_monthly.csv", parse_dates=["month_end"]).assign(idx="500")
    b = pd.read_csv(M01 / "membership_monthly.csv", parse_dates=["month_end"]).assign(idx="400")
    m = pd.concat([a, b], ignore_index=True)
    # a name that moved 400->500 in a month appears twice; keep the 500 row
    return m.sort_values(["month_end", "ticker", "idx"], ascending=[True, True, False]).drop_duplicates(
        ["month_end", "ticker"])


def close():
    """Adjusted (total-return) closes for S&P 500+400 names, m11 merge of m01 + own fetch (read-only)."""
    return pd.read_pickle(M11 / "close.pkl")


def bench():
    return pd.read_pickle(M01 / "bench_close.pkl")
