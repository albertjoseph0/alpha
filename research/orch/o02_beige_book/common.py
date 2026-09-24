"""Shared signal code: per-release ETF scores (Jev, dictionary, LM), 12-1 momentum, and the top-K rule.

Universe: the 9 original Select Sector SPDRs (listed 1998-12). XLRE (2015) and XLC (2018) are excluded so DEV and TEST
use the same universe.
Mapping (fixed at hand-over, before any results):
    XLY = consumer                     XLF = banking            XLE = energy          XLK = services
    XLI = mean(manufacturing, transport)
    XLB = mean(manufacturing, construction), construction = mean(resi_re, cre)
    XLP = XLV = XLU = -overall         (defensives win when overall activity is weakening)
A sector the report does not describe (NaN) takes the edition's `overall` score.
"""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
D = ROOT / "data" / "orch" / "o02_beige_book"
ETFS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
DEFENSIVE = ["XLP", "XLU", "XLV"]
SECTOR_KEYS = ["overall", "consumer", "manufacturing", "resi_re", "cre", "banking", "energy", "agriculture",
               "services", "transport", "labor", "prices"]
K = 3                      # ETFs held (fixed a priori; same K as the momentum baseline)
LOOKBACK, SKIP = 252, 21   # 12-1 momentum


def etf_scores(sec: pd.DataFrame) -> pd.DataFrame:
    """sec: rows = release, columns = SECTOR_KEYS (direction scores). Returns rows = release, columns = ETFS."""
    s = sec[SECTOR_KEYS].copy()
    for k in SECTOR_KEYS:
        if k != "overall":
            s[k] = s[k].fillna(s["overall"])
    s["overall"] = s["overall"].fillna(0.0)
    s = s.fillna(0.0)
    constr = (s.resi_re + s.cre) / 2
    out = pd.DataFrame({
        "XLY": s.consumer, "XLF": s.banking, "XLE": s.energy, "XLK": s.services,
        "XLI": (s.manufacturing + s.transport) / 2,
        "XLB": (s.manufacturing + constr) / 2,
        "XLP": -s.overall, "XLU": -s.overall, "XLV": -s.overall,
    }, index=s.index)
    return out[ETFS]


def load_text_scores() -> dict:
    """{'jev': ..., 'dict': ..., 'lm': ...} ETF score tables indexed by release date (Timestamp)."""
    out = {}
    if (D / "jev_scores.parquet").exists():
        j = pd.read_parquet(D / "jev_scores.parquet")
        j.index = pd.to_datetime(j.release)
        out["jev"] = etf_scores(j)
    dct = pd.read_parquet(D / "dict_scores.parquet")
    dct.index = pd.to_datetime(dct.release)
    out["dict"] = etf_scores(dct.rename(columns={"d_" + k: k for k in SECTOR_KEYS}))
    out["lm"] = etf_scores(dct[["lm_" + k for k in SECTOR_KEYS]].rename(columns={"lm_" + k: k for k in SECTOR_KEYS}))
    return out


def releases() -> pd.DatetimeIndex:
    j = pd.read_parquet(D / "dict_scores.parquet")
    return pd.DatetimeIndex(pd.to_datetime(j.release)).sort_values()


def rebalance_days(cal: pd.DatetimeIndex, rel: pd.DatetimeIndex) -> pd.Series:
    """Map each release to its decision day: the first trading day strictly after the release date.
    (The report is public at 14:00 ET on the release day; the harness then trades one day later still.)"""
    pos = cal.searchsorted(rel, side="right")
    ok = pos < len(cal)
    return pd.Series(cal[pos[ok]], index=rel[ok])


def momentum(R: pd.DataFrame) -> pd.DataFrame:
    """12-1 total-return momentum (log), NaN unless >= 250 valid days in the last 252."""
    v = R.to_numpy(dtype=np.float64)
    ok = ~np.isnan(v)
    lp = np.cumsum(np.log1p(np.where(ok, v, 0.0)), axis=0)
    cnt = np.cumsum(ok, axis=0)
    n = len(R)
    mom = np.full_like(lp, np.nan)
    if n > LOOKBACK:
        t = np.arange(LOOKBACK, n)
        mom[t] = lp[t - SKIP] - lp[t - LOOKBACK]
        valid = (cnt[t] - cnt[t - LOOKBACK]) >= 250
        mom[t] = np.where(valid, mom[t], np.nan)
    return pd.DataFrame(mom, index=R.index, columns=R.columns)


def pct_rank(x: pd.Series) -> pd.Series:
    return x.rank(method="average", pct=True)


def top_k(score: pd.Series, k: int = K) -> pd.Series:
    """Equal weight 1/k on the k best scores; a tie group straddling the cut shares the remaining slots."""
    s = score.dropna()
    w = pd.Series(0.0, index=score.index)
    if len(s) < k:
        return w * np.nan
    s = s.round(10)
    kth = s.sort_values(ascending=False).iloc[k - 1]
    above = s[s > kth].index
    tied = s[s == kth].index
    w[above] = 1.0 / k
    w[tied] = (k - len(above)) / k / len(tied)
    return w


def composite(parts: list) -> pd.Series:
    """Sum of cross-sectional percentile ranks (equal weights, no fitted parameters)."""
    return sum(pct_rank(p) for p in parts)
