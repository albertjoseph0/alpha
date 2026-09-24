"""Beige Book sector rotation (o02). Harness strategy over the 9 Select Sector SPDRs.

Each Beige Book release r gets a decision day: the first trading day after r. The harness then adds its own
1-day lag, so trades happen at the close two trading days after the release. On that decision day the target is:
    top-K (K=3) ETFs, equal weight, by the variant's score (see common.py for the sector->ETF mapping).
The target is held (re-issued every day, so the engine re-balances drift back to it at harness costs) until
the next release's decision day. Variants:
    ew            equal weight 9 sectors (benchmark)
    mom           12-1 momentum (feature set a: no text)
    dict / lm     dictionary tone of sector sentences (text baseline; dict = primary, lm = secondary)
    jev           Jev direction-of-change scores (the idea as stated)
    mom+dict, mom+dict+jev, mom+jev, dict+jev: sums of cross-sectional percentile ranks (nested sets)
Run:  O02_VARIANT=jev .venv/bin/python -m harness research/orch/o02_beige_book/strategy.py --window etf_dev
The default variant (no env var) is the pre-registered one (PREREG.md).
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import ETFS, K, composite, load_text_scores, momentum, rebalance_days, releases, top_k  # noqa: E402
from harness import Strategy  # noqa: E402

PREREG_VARIANT = "jev"


class BeigeBookRotation(Strategy):
    refit_every = None

    def __init__(self, variant: str = PREREG_VARIANT, k: int = K):
        self.variant, self.k = variant, k
        self.name = f"o02:beige_{variant}_top{k}"
        self.text = load_text_scores()
        self.rel = releases()

    def target(self, r: pd.Timestamp, mom_row: pd.Series) -> pd.Series:
        if self.variant == "ew":
            return pd.Series(1.0 / len(ETFS), index=ETFS)
        parts = []
        for p in self.variant.split("+"):
            parts.append(mom_row if p == "mom" else self.text[p].loc[r])
        score = parts[0] if len(parts) == 1 else composite(parts)
        if any(p.isna().all() for p in parts):
            return pd.Series(np.nan, index=ETFS)
        return top_k(score, self.k)

    def predict(self, data, dates):
        R = data.returns[ETFS]
        cal = data.dates
        mom = momentum(R)
        reb = rebalance_days(cal, self.rel)          # release -> decision day (only those <= data end)
        out = pd.DataFrame(np.nan, index=dates, columns=ETFS)
        if len(reb) == 0:
            return out
        dd = pd.DatetimeIndex(reb.values)
        # latest release whose decision day <= d
        idx = dd.searchsorted(dates, side="right") - 1
        cache = {}
        for row, i in enumerate(idx):
            if i < 0:
                continue
            if i not in cache:
                r, d0 = reb.index[i], dd[i]
                cache[i] = self.target(r, mom.loc[d0])
            out.iloc[row] = cache[i].to_numpy()
        return out


def build_strategy():
    return BeigeBookRotation(os.environ.get("O02_VARIANT", PREREG_VARIANT), int(os.environ.get("O02_K", K)))
