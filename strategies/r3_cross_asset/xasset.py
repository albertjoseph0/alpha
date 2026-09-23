"""Parameterised cross-asset momentum engine used for research (strategy.py fixes the params)."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd
from harness import Strategy, etf_meta

GROUP = {"us_equity": "us", "sector": "us", "industry": "us", "options": "us",
         "intl_equity": "intl", "bond": "bond", "real_asset": "real", "volatility": "vol"}
DEFENSIVE = ("SHY", "IEF", "TLT", "TIP", "GLD")
TRANCHE_DAYS = (0, 5, 10, 15)


def _meta():
    m = etf_meta()
    if "ticker" in m.columns:
        m = m.set_index("ticker")
    return m


class XAsset(Strategy):
    refit_every = None

    def __init__(self, lookbacks=(252,), skip=21, frac=0.2, weighting="rank", abs_filter=False,
                 defensive=False, n_def=2, group_cap=None, exclude=("VIXY",), vol_win=63, trend_lbs=None, score="mom", gate="avg", max_corr=None, corr_win=126,
                 name="r3:xasset_research"):
        self.lookbacks, self.skip, self.frac = tuple(lookbacks), skip, frac
        self.weighting, self.abs_filter, self.defensive, self.n_def = weighting, abs_filter, defensive, n_def
        self.group_cap, self.exclude, self.vol_win, self.name = group_cap, set(exclude), vol_win, name
        self.score, self.gate = score, gate
        self.max_corr, self.corr_win = max_corr, corr_win
        self.trend_lbs = None if trend_lbs is None else tuple(trend_lbs)

    def predict(self, data, dates):
        R = data.returns
        cols = list(R.columns)
        meta = _meta()
        grp = np.array([GROUP.get(meta.loc[c, "asset_class"], "other") if c in meta.index else "other"
                        for c in cols])
        vals = R.to_numpy(dtype=np.float64)
        ok = ~np.isnan(vals)
        x = np.where(ok, vals, 0.0)
        lp = np.cumsum(np.log1p(x), axis=0)
        cnt = np.cumsum(ok, axis=0)
        rf = data.rf.reindex(R.index).fillna(0.0).to_numpy(dtype=np.float64)
        lrf = np.cumsum(np.log1p(rf))
        sq = np.cumsum(x * x, axis=0)
        s1 = np.cumsum(x, axis=0)
        cal = data.dates
        mkey = cal.year.to_numpy() * 12 + cal.month.to_numpy()
        ms_idx = np.flatnonzero(np.r_[True, mkey[1:] != mkey[:-1]])
        last = int(cal.get_indexer([dates[-1]])[0])
        first = int(cal.get_indexer([dates[0]])[0])
        L = max(self.lookbacks)
        events = sorted((i + off, j) for j, off in enumerate(TRANCHE_DAYS) for i in ms_idx
                        if i >= L + 1 and i + off <= last)
        excl = np.array([c in self.exclude for c in cols])
        dmask = np.array([c in DEFENSIVE for c in cols])
        n = len(cols)
        tranche_w, targets = {}, {}
        for t, j in events:
            valid = (cnt[t] - cnt[t - L] >= L - 2) & (cnt[t] - cnt[t - 5] >= 5)
            # momentum: average of lookbacks, excess of T-bills over the same window
            mom = np.zeros(n); ex = np.zeros(n)
            for lb in self.lookbacks:
                m = lp[t - self.skip] - lp[t - lb]
                mom += m / len(self.lookbacks)
                ex += (m - (lrf[t - self.skip] - lrf[t - lb])) / len(self.lookbacks)
            if self.trend_lbs is not None:  # time-series trend: blended excess log return, no skip
                ex = np.zeros(n); vote = np.zeros(n)
                for lb in self.trend_lbs:
                    e = (lp[t] - lp[t - lb]) - (lrf[t] - lrf[t - lb])
                    ex += e / len(self.trend_lbs)
                    vote += (e > 0) / len(self.trend_lbs)
            V = self.vol_win
            mu = (s1[t] - s1[t - V]) / V
            vol = np.sqrt(np.maximum((sq[t] - sq[t - V]) / V - mu * mu, 1e-10))
            risky = np.flatnonzero(valid & ~excl)
            if len(risky) < 5:
                continue
            k = max(1, int(round(len(risky) * self.frac)))
            sc = mom
            if self.score == "sharpe":  # risk-adjusted momentum: 12-1 return / 252d vol
                mu2 = (s1[t] - s1[t - 252]) / 252
                v2 = np.sqrt(np.maximum((sq[t] - sq[t - 252]) / 252 - mu2 * mu2, 1e-10))
                sc = mom / v2
            order = risky[np.argsort(-sc[risky], kind="stable")]
            picked, gcount = [], {}
            if self.max_corr is not None:
                C = np.corrcoef(x[t - self.corr_win + 1: t + 1].T)
            cap = None if self.group_cap is None else max(1, int(np.ceil(k * self.group_cap)))
            for a in order:
                if len(picked) >= k:
                    break
                if cap is not None and gcount.get(grp[a], 0) >= cap:
                    continue
                if self.max_corr is not None and picked and C[a, picked].max() > self.max_corr:
                    continue  # near-duplicate of a stronger holding
                picked.append(a); gcount[grp[a]] = gcount.get(grp[a], 0) + 1
            rw = np.zeros(n)
            kk = len(picked)
            # rank weights over the full k slots; unfilled slots keep their share for the fallback
            slot = np.arange(k, 0, -1, dtype=np.float64); slot /= slot.sum()
            for r, a in enumerate(picked):
                if self.gate == "vote":  # graded: slot share = fraction of horizons trending up
                    rw[a] = slot[r] * vote[a]
                elif not (self.abs_filter and ex[a] <= 0):  # dual momentum: failed slot -> fallback
                    rw[a] = slot[r]
            picked = [a for a in picked if rw[a] > 0]
            if self.weighting == "rank_iv" and picked:
                p = np.array(picked)
                iv = rw[p] / vol[p]
                rw[p] = iv / iv.sum() * rw[p].sum()
            spare = 1.0 - rw.sum()
            if spare > 1e-12 and self.defensive:
                dpass = (vote > 0.5) if self.gate == "vote" else (ex > 0)
                d = np.flatnonzero(valid & dmask & dpass)
                if len(d):
                    d = d[np.argsort(-mom[d], kind="stable")][: self.n_def]
                    rw[d] += spare / len(d)
            tranche_w[j] = rw
            tw = sum(tranche_w.values()) / len(tranche_w)
            targets[t] = tw
        out = pd.DataFrame(np.nan, index=dates, columns=cols)
        pos = cal.get_indexer(dates)
        for r, p in enumerate(pos):
            if p in targets:
                out.iloc[r] = targets[p]
        return out
