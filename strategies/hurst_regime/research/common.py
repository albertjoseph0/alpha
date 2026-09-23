"""Shared research helpers (dev data only, via harness.load_dev)."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))           # strategy dir (hurst.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # repo root
from harness import load_dev, ASSETS  # noqa: E402


def block_sums(lr: np.ndarray, b: int) -> np.ndarray:
    """Non-overlapping sums of b rows anchored at row 0 (drops incomplete tail)."""
    k = len(lr) // b
    return lr[: k * b].reshape(k, b, *lr.shape[1:]).sum(axis=1)


def get():
    d = load_dev()
    lr = np.log1p(d.returns[ASSETS]).to_numpy()
    return d, lr
