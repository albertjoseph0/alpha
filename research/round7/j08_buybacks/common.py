"""Shared helpers for j08 (buyback announcements read by Jev). Paths, EDGAR access, periods."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("MKL_NUM_THREADS", "1")
import gzip, json, sys, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/home/user/alpha")
RES = ROOT / "research/round7/j08_buybacks"
DATA = ROOT / "data/round7/j08_buybacks"
DATA.mkdir(parents=True, exist_ok=True)
M06 = ROOT / "data/round5/m06_filing_reader"
M11 = ROOT / "data/round5/m11_tree_ranker"
M01 = ROOT / "data/round5/m01_midcap_momentum"
sys.path.insert(0, str(ROOT / "research/round5"))
from sec import get  # noqa: E402  shared, rate-limited EDGAR fetcher (never call sec.gov directly)

AGENT = "j08"
DEV = ("2013-01-01", "2019-12-31")     # announcements (and DEV portfolio evaluation window)
TEST = ("2020-01-01", "2026-12-31")    # sealed until PREREG.md exists


def efts(q, start, end, frm=0, forms="8-K"):
    p = dict(q=q, forms=forms, dateRange="custom", startdt=start, enddt=end)
    if frm:
        p["from"] = frm
    return json.loads(get("https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(p)))


def read_jsonl(path):
    """Read a jsonl.gz tolerating a partially written tail."""
    out = []
    try:
        with gzip.open(path, "rt") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    break
    except (EOFError, OSError, FileNotFoundError):
        pass
    return out
