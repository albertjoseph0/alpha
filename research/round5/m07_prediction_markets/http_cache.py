"""Polite cached HTTP GET for Kalshi / Polymarket public APIs.

Every response is cached (gzip JSON) under data/round5/m07_prediction_markets/cache/<host>/<sha1>.json.gz
so reruns never hit the network.  Sleeps between live requests and backs off on 429/5xx.
"""
import gzip
import hashlib
import json
import os
import time
import urllib.parse

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
CACHE = os.path.join(ROOT, "data/round5/m07_prediction_markets/cache")
_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "alpha-research contact@alpha-research.dev"
_last = {"t": 0.0}
MIN_GAP = float(os.environ.get("M07_MIN_GAP", "0.25"))


def _path(url):
    host = urllib.parse.urlparse(url).netloc
    h = hashlib.sha1(url.encode()).hexdigest()
    d = os.path.join(CACHE, host, h[:2])
    return os.path.join(d, h + ".json.gz")


def get(url, params=None, cache=True, tries=8):
    if params:
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = url + ("&" if "?" in url else "?") + q
    p = _path(url)
    if cache and os.path.exists(p):
        with gzip.open(p, "rt") as f:
            return json.load(f)
    delay = 1.0
    for i in range(tries):
        gap = time.time() - _last["t"]
        if gap < MIN_GAP:
            time.sleep(MIN_GAP - gap)
        _last["t"] = time.time()
        try:
            r = _SESSION.get(url, timeout=60)
        except requests.RequestException:
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        if r.status_code == 200:
            data = r.json()
            if cache:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with gzip.open(p, "wt") as f:
                    json.dump(data, f)
            return data
        if r.status_code in (404, 400):
            data = {"_error": r.status_code, "_body": r.text[:500]}
            if cache:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with gzip.open(p, "wt") as f:
                    json.dump(data, f)
            return data
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError(f"failed {url}: {r.status_code} {r.text[:200]}")
