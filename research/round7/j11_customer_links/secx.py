"""Thin wrapper over the shared sec.get: use the shared cache only when the URL is already cached,
otherwise fetch without caching (keeps the shared cache from growing with our big 10-K documents)."""
import hashlib
from common import ROOT
from sec import get, CACHE


def cached(url: str) -> bool:
    key = hashlib.sha256(url.encode()).hexdigest()
    return (CACHE / key[:2] / f"{key}.gz").exists()


def fetch(url: str, store: bool = False) -> str:
    return get(url, cache=(store or cached(url)))
