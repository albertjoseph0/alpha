"""m11 shared paths and small helpers."""
import os
import pathlib

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "round5" / "m11_tree_ranker"
OUT = pathlib.Path(__file__).resolve().parent
M01 = ROOT / "data" / "round5" / "m01_midcap_momentum"
M06 = ROOT / "data" / "round5" / "m06_filing_reader"
M05 = ROOT / "data" / "round5" / "m05_insider_clusters"
DATA.mkdir(parents=True, exist_ok=True)

SECTOR_ETFS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]  # all exist since 1998


def norm_ticker(x):
    if not isinstance(x, str) or not x.strip() or x.strip().lower() == "nan":
        return None
    return x.strip().replace(".", "-").upper()


def cagr_m(r):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (12 / len(r)) - 1


def maxdd(r):
    eq = (1 + pd.Series(r).dropna()).cumprod()
    return (eq / eq.cummax() - 1).min()
