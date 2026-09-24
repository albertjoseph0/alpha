"""Same as chain_check_linz.py but with the trailing 21-day mean SKEW (the round-5b base surface input)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import chain_check_linz as c  # noqa: E402

_orig = pd.read_pickle


def patched(path, *a, **k):
    df = _orig(path, *a, **k)
    if str(path).endswith("panel.pkl"):
        df = df.copy()
        df["SKEW"] = df["SKEW"].rolling(21, min_periods=1).mean()
    return df


pd.read_pickle = patched
c.OUT = Path(__file__).parent / "_tmp_s21"
c.OUT.mkdir(exist_ok=True)
c.main()
(c.OUT / "chain_check_linz.csv").rename(Path(__file__).parent / "chain_check_linz_s21.csv")
c.OUT.rmdir()
