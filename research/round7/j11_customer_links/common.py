"""j11 customer-links momentum: shared paths and helpers."""
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
DATA = ROOT / "data" / "round7" / "j11_customer_links"
OUT = pathlib.Path(__file__).resolve().parent
M11 = ROOT / "data" / "round5" / "m11_tree_ranker"
M06 = ROOT / "data" / "round5" / "m06_filing_reader"
M05 = ROOT / "data" / "round5" / "m05_insider_clusters"
M01 = ROOT / "data" / "round5" / "m01_midcap_momentum"
J01 = ROOT / "data" / "round6" / "j01_lazy_prices"
DATA.mkdir(parents=True, exist_ok=True)
AGENT = "j11"

DEV_START, DEV_END = "2013-01-01", "2019-12-31"
TEST_START = "2020-01-01"


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


def md(df, fmt=None):
    """DataFrame -> markdown table."""
    df = pd.DataFrame(df)
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in df.iterrows():
        vals = [(fmt.format(v) if (fmt and isinstance(v, float)) else str(v)) for v in r.values]
        out.append("| " + " | ".join([str(i)] + vals) + " |")
    return "\n".join(out)
