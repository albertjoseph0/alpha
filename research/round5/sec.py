"""Shared, cross-process rate-limited SEC EDGAR fetcher (all agents on this machine share one budget).

The SEC's fair-access limit is 10 requests/s per IP, and exceeding it gets the IP blocked for ~10 minutes.
Every agent calling EDGAR through this module shares a global budget of GLOBAL_RPS requests/s,
enforced with a file lock, so several agents can fetch concurrently without tripping the limit.

    from sec import get
    txt = get("https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106.txt")

Responses are cached under data/round5/sec_cache/ (by URL hash), so repeated fetches are free.
Pass cache=False for index pages that change (e.g. the current quarter's form.idx).
"""
import fcntl
import gzip
import http.client
import hashlib
import pathlib
import time
import urllib.error
import urllib.request

UA = "alpha-research contact@alpha-research.dev"
GLOBAL_RPS = 4.0            # shared by all agents using this module (other legacy fetchers use the rest)
ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "round5" / "sec_cache"
LOCK = CACHE / "_rate.lock"


def _wait_turn() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        s = f.read().strip()
        last = float(s) if s else 0.0
        now = time.time()
        nxt = max(now, last + 1.0 / GLOBAL_RPS)
        if nxt > now:
            time.sleep(nxt - now)
        f.seek(0)
        f.truncate()
        f.write(repr(nxt))
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def get(url: str, cache: bool = True, retries: int = 5, timeout: float = 60.0) -> str:
    key = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE / key[:2] / f"{key}.gz"
    if cache and path.exists():
        return gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
    delay = 5.0
    for attempt in range(retries):
        _wait_turn()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay *= 2; continue
            raise
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionError):
            if attempt < retries - 1:
                time.sleep(delay); delay *= 2; continue
            raise
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data))
    return data.decode("utf-8", errors="replace")


if __name__ == "__main__":
    t = time.time()
    for q in (1, 2, 3):
        s = get(f"https://www.sec.gov/Archives/edgar/full-index/2015/QTR{q}/form.idx")
        print(q, len(s))
    print("elapsed", round(time.time() - t, 2))
