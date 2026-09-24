"""j06 governance / pay-alignment index from DEF 14A proxies: shared paths and helpers."""
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
DATA = ROOT / "data" / "round6" / "j06_governance"
OUT = pathlib.Path(__file__).resolve().parent
M11 = ROOT / "data" / "round5" / "m11_tree_ranker"
M01 = ROOT / "data" / "round5" / "m01_midcap_momentum"
J01 = ROOT / "data" / "round6" / "j01_lazy_prices"
DATA.mkdir(parents=True, exist_ok=True)
AGENT = "j06"

SEASONS = list(range(2013, 2026))          # proxy season Y -> portfolio formed first trading day of July Y
DEV_SEASONS = list(range(2013, 2020))      # 2013..2019 (holding periods end 2020-06-30)
TEST_SEASONS = list(range(2020, 2026))     # 2020..2025 (sealed; holding periods end 2026-06-30)


def load_close():
    C = pd.read_pickle(M11 / "close.pkl")
    C = C.loc[:, ~C.columns.duplicated()]
    cal = C["SPY"].dropna().index
    return C.reindex(cal).astype("float64")


def formation_dates(cal):
    """Season Y -> (formation date = first trading day of July Y, exit = first trading day of July Y+1)."""
    out = {}
    for y in SEASONS + [SEASONS[-1] + 1]:
        d = cal[cal >= pd.Timestamp(f"{y}-07-01")]
        if len(d):
            out[y] = d[0]
    return out


def cagr_from_years(r):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (1 / len(r)) - 1 if len(r) else np.nan


def maxdd(eq):
    eq = pd.Series(eq).dropna()
    return (eq / eq.cummax() - 1).min()
