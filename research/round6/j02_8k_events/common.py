"""Shared helpers for j02 (8-K material-event drift). Paths, EDGAR access, universe."""
import gzip, hashlib, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path("/home/user/alpha")
RES = ROOT / "research/round6/j02_8k_events"
DATA = ROOT / "data/round6/j02_8k_events"
DATA.mkdir(parents=True, exist_ok=True)
M06 = ROOT / "data/round5/m06_filing_reader"
sys.path.insert(0, str(ROOT / "research/round5"))
from sec import get  # noqa: E402  shared, rate-limited EDGAR fetcher

AGENT = "j02"
ITEMS = ["1.01", "1.02", "2.01", "2.05", "2.06", "3.01", "4.01", "4.02", "5.02", "7.01", "8.01"]
DEV = ("2019-10-01", "2022-12-31")
TEST = ("2023-01-01", "2026-12-31")


def edgar(url):
    """EDGAR text. Reads m06's read-only cache first (already-fetched submissions JSON), else sec.get."""
    k = hashlib.sha1(url.encode()).hexdigest()
    p = M06 / "cache" / k[:2] / (k + ".gz")
    if p.exists():
        return gzip.decompress(p.read_bytes()).decode("utf-8", "replace")
    return get(url)


def read_texts(path=None):
    """Read texts.jsonl.gz tolerating a partially written tail (the fetcher may be running)."""
    if path is None:  # DEV texts + TEST texts (fetched by two processes into separate files)
        out = []
        for f in ["texts.jsonl.gz", "texts_dev2.jsonl.gz", "texts_test.jsonl.gz", "texts_test2.jsonl.gz"]:
            out += read_texts(DATA / f)
        return out
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
