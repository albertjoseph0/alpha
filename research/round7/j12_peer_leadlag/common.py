"""j12 peer lead-lag: shared paths and helpers."""
import os
import pathlib
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
DATA = ROOT / "data" / "round7" / "j12_peer_leadlag"
OUT = pathlib.Path(__file__).resolve().parent
M11 = ROOT / "data" / "round5" / "m11_tree_ranker"
M06 = ROOT / "data" / "round5" / "m06_filing_reader"
M05 = ROOT / "data" / "round5" / "m05_insider_clusters"
M01 = ROOT / "data" / "round5" / "m01_midcap_momentum"
J01 = ROOT / "data" / "round6" / "j01_lazy_prices"
DATA.mkdir(parents=True, exist_ok=True)
AGENT = "j12"

DEV_START, DEV_END = "2013-01-01", "2019-12-31"
TEST_START = "2020-01-01"
FORM_MONTH = 4   # peer sets are formed at the end of April each year (after Dec-FYE 10-Ks are filed)


def norm_ticker(x):
    if not isinstance(x, str) or not x.strip() or x.strip().lower() == "nan":
        return None
    return x.strip().replace(".", "-").upper()


def cagr_m(r):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (12 / len(r)) - 1


def maxdd(r):
    eq = (1 + pd.Series(r).dropna()).cumprod()
    return float((eq / eq.cummax() - 1).min())
