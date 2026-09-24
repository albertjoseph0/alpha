"""Shared helpers for m06_filing_reader: paths, polite cached SEC fetcher."""
import os, time, json, hashlib, gzip
from pathlib import Path
import requests

ROOT = Path("/home/user/alpha")
RES = ROOT / "research/round5/m06_filing_reader"
DATA = ROOT / "data/round5/m06_filing_reader"
CACHE = DATA / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

UA = "alpha-research contact@alpha-research.dev"
_S = requests.Session()
_S.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
_last = [0.0]
MIN_GAP = 0.22  # seconds between requests -> < 5 req/s


def fetch(url, cache=True, binary=False, retries=4):
    """GET with on-disk gzip cache and a global rate limit (<5 req/s)."""
    key = hashlib.sha1(url.encode()).hexdigest()
    p = CACHE / key[:2] / (key + ".gz")
    if cache and p.exists():
        with gzip.open(p, "rb") as f:
            b = f.read()
        return b if binary else b.decode("utf-8", "replace")
    for k in range(retries):
        dt = time.time() - _last[0]
        if dt < MIN_GAP:
            time.sleep(MIN_GAP - dt)
        _last[0] = time.time()
        try:
            r = _S.get(url, timeout=30)
        except Exception:
            time.sleep(2 * (k + 1)); continue
        if r.status_code == 200:
            b = r.content
            if cache:
                p.parent.mkdir(exist_ok=True)
                with gzip.open(p, "wb") as f:
                    f.write(b)
            return b if binary else b.decode("utf-8", "replace")
        if r.status_code == 404:
            return None
        time.sleep(3 * (k + 1))  # 429/403/5xx: back off
    return None
