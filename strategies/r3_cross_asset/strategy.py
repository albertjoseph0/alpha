"""r3:xasset_dualmom_volcap -- cross-asset dual momentum with a per-position volatility cap.

Universe: every ETF in the round-3 universe except VIXY (long VIX futures: structural negative carry).
Each of 4 staggered monthly tranches (trading day 0/5/10/15 of the month) does:
  1. Relative strength: rank eligible ETFs (>= 250 valid days in the last 252, last 5 valid) by
     12-1 momentum (log return t-252 -> t-21). Take the top fifth, k = round(n/5), rank-weighted
     (best gets k, k-th gets 1, normalised to 1).
  2. Trend gate (absolute momentum): a pick keeps its slot only if its blended excess return over
     T-bills, averaged over 1, 3 and 12 months (21/63/252 days, no skip), is positive.
  3. Volatility cap: each kept slot is scaled by min(1, 20% / annualised 63-day vol), so volatile
     winners (silver, miners, single EM countries, commodities in a crash) cannot dominate the book.
  4. Everything freed by steps 2-3 goes to the two defensive ETFs (SHY, IEF, TLT, TIP, GLD) with
     the highest 12-1 momentum among those whose own trend gate passes; if none passes, cash.
The portfolio is the equal average of the four tranches. Long only, sum of weights <= 1.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

from harness import MarketData, Strategy

EXCLUDE = ("VIXY",)
DEFENSIVE = ("SHY", "IEF", "TLT", "TIP", "GLD")
TRANCHE_DAYS = (0, 5, 10, 15)
LOOKBACK, SKIP = 252, 21          # 12-1 relative strength
TREND_LBS = (21, 63, 252)         # 1/3/12-month absolute trend gate
FRAC = 1 / 5                      # share of eligible ETFs held
VOL_WIN, VOL_CAP = 63, 0.20       # per-position annualised vol cap
N_DEF = 2                         # defensive ETFs that share the freed weight


class XAssetDualMomVolCap(Strategy):
    name = "r3:xasset_dualmom_volcap"
    refit_every = None

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.returns
        cols = list(R.columns)
        n = len(cols)
        vals = R.to_numpy(dtype=np.float64)
        ok = ~np.isnan(vals)
        x = np.where(ok, vals, 0.0)
        lp = np.cumsum(np.log1p(x), axis=0)
        cnt = np.cumsum(ok, axis=0)
        s1 = np.cumsum(x, axis=0)
        s2 = np.cumsum(x * x, axis=0)
        rf = data.rf.reindex(R.index).fillna(0.0).to_numpy(dtype=np.float64)
        lrf = np.cumsum(np.log1p(rf))
        excl = np.array([c in EXCLUDE for c in cols])
        dmask = np.array([c in DEFENSIVE for c in cols])

        cal = data.dates
        mkey = cal.year.to_numpy() * 12 + cal.month.to_numpy()
        ms_idx = np.flatnonzero(np.r_[True, mkey[1:] != mkey[:-1]])
        last = int(cal.get_indexer([dates[-1]])[0])
        events = sorted((i + off, j) for j, off in enumerate(TRANCHE_DAYS) for i in ms_idx
                        if i >= LOOKBACK + 1 and i + off <= last)

        slots_cache = {}
        tranche_w, targets = {}, {}
        for t, j in events:
            valid = (cnt[t] - cnt[t - LOOKBACK] >= LOOKBACK - 2) & (cnt[t] - cnt[t - 5] >= 5)
            risky = np.flatnonzero(valid & ~excl)
            if len(risky) < 5:
                continue
            mom = lp[t - SKIP] - lp[t - LOOKBACK]
            trend = np.zeros(n)
            for lb in TREND_LBS:
                trend += ((lp[t] - lp[t - lb]) - (lrf[t] - lrf[t - lb])) / len(TREND_LBS)
            mu = (s1[t] - s1[t - VOL_WIN]) / VOL_WIN
            vol = np.sqrt(np.maximum((s2[t] - s2[t - VOL_WIN]) / VOL_WIN - mu * mu, 1e-10) * 252.0)

            k = max(1, int(round(len(risky) * FRAC)))
            if k not in slots_cache:
                sl = np.arange(k, 0, -1, dtype=np.float64)
                slots_cache[k] = sl / sl.sum()
            picks = risky[np.argsort(-mom[risky], kind="stable")][:k]
            w = np.zeros(n)
            w[picks] = slots_cache[k] * (trend[picks] > 0) * np.minimum(1.0, VOL_CAP / vol[picks])

            spare = 1.0 - w.sum()
            if spare > 1e-12:
                d = np.flatnonzero(valid & dmask & (trend > 0))
                if len(d):
                    d = d[np.argsort(-mom[d], kind="stable")][:N_DEF]
                    w[d] += spare / len(d)
            tranche_w[j] = w
            targets[t] = sum(tranche_w.values()) / len(tranche_w)

        out = pd.DataFrame(np.nan, index=dates, columns=cols)
        pos = cal.get_indexer(dates)
        for r, p in enumerate(pos):
            if p in targets:
                out.iloc[r] = targets[p]
        return out
