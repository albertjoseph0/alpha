"""j07 shared paths and helpers (SEC comment letters read by Jev)."""
import gzip
import http.client
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "round6" / "j07_comment_letters"
M11 = ROOT / "data" / "round5" / "m11_tree_ranker"
M06 = ROOT / "data" / "round5" / "m06_filing_reader"
J01 = ROOT / "data" / "round6" / "j01_lazy_prices"
DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "research" / "round5"))
import sec  # noqa: E402  (shared, cross-process rate limiter + UA)

AGENT = "j07"
DEV_START, DEV_END = pd.Timestamp("2012-01-01"), pd.Timestamp("2019-12-31")
TEST_START = pd.Timestamp("2020-01-01")


def fetch(url: str, retries: int = 6, timeout: float = 90.0) -> bytes:
    """Raw SEC fetch through the shared rate limiter (sec._wait_turn), gzip transfer, no disk cache.
    Used for big daily-index files and binary PDFs that we reduce to compact text right away."""
    delay = 5.0
    for attempt in range(retries):
        sec._wait_turn()
        req = urllib.request.Request(url, headers={"User-Agent": sec.UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay = min(delay * 2, 120); continue
            raise
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionError, OSError):
            if attempt < retries - 1:
                time.sleep(delay); delay = min(delay * 2, 120); continue
            raise


def norm_ticker(x):
    if not isinstance(x, str) or not x.strip() or x.strip().lower() == "nan":
        return None
    return x.strip().replace(".", "-").upper()


def cagr_m(r):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (12 / len(r)) - 1 if len(r) else np.nan


def maxdd(r):
    eq = (1 + pd.Series(r).dropna()).cumprod()
    return (eq / eq.cummax() - 1).min()


def md(df, floatfmt="{:.3f}"):
    """DataFrame -> markdown table (no tabulate dependency)."""
    df = pd.DataFrame(df)
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for i, r in df.iterrows():
        vals = [floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r.values]
        out.append("| " + " | ".join([str(i)] + vals) + " |")
    return "\n".join(out)
