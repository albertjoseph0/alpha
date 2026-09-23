"""r3:eqrot -- cross-sectional momentum rotation across the equity-ETF sleeve.

Universe (equity groups only): US size/style funds, SPDR sectors, industry funds,
international country/region funds and US REITs (VNQ). Everything else is excluded from
ranking; IEF (7-10y Treasuries) is the only non-equity holding, used as the fallback.

Rule, evaluated per tranche (four tranches refreshed on trading days 0/5/10/15 of each month,
portfolio = equal average of the tranches, as in r2:construct_rank5_stag4):
  1. signal: 12-1 month momentum, log total-return change t-252 -> t-21 trading days;
     eligible = >= 250 valid days in the last 252 and valid on each of the last 5 days;
  2. k = max(K_MIN, round(n_eligible * FRAC)) holdings;
  3. de-duplication: walk down the ranking and skip a candidate whose 252-day daily-return
     correlation with an already chosen ETF exceeds MAX_CORR (so SPY/IWF/QQQ/XLK-style
     near-duplicates do not fill several slots);
  4. weights linear in rank among the k picks (best = k, ..., k-th = 1), normalised;
  5. absolute-trend check: a pick whose 6-month return (t-126 -> t, no skip) does not beat
     T-bills over the same window hands its weight to IEF (or to T-bill cash if IEF is not
     listed or itself fails the same check).
Long only, no leverage. Final configuration = research.py config "trend6" (see README.md).
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

from harness import Strategy, etf_meta

EQUITY_CLASSES = ("us_equity", "sector", "industry", "intl_equity")
EXTRA_EQUITY = ("VNQ",)
FALLBACK = "IEF"
LOOKBACK, SKIP = 252, 21
TRANCHE_DAYS = (0, 5, 10, 15)


def equity_universe():
    m = etf_meta()
    return [t for t in m.index if m.loc[t, "asset_class"] in EQUITY_CLASSES or t in EXTRA_EQUITY]


class EquityRotation(Strategy):
    name = "r3:eqrot_mom12_dedup90_rank5_stag4_trend6IEF"
    refit_every = None

    def __init__(self, frac=1 / 5, k_min=3, max_corr=0.90, rank_weight=True,
                 tranche_days=TRANCHE_DAYS, trend=True, fallback=FALLBACK, universe=None, name=None,
                 score="mom", trend_lb=126, blend=True):
        self.score, self.trend_lb, self.blend = score, trend_lb, blend
        self.frac, self.k_min, self.max_corr, self.rank_weight = frac, k_min, max_corr, rank_weight
        self.tranche_days, self.trend, self.fallback = tuple(tranche_days), trend, fallback
        self.universe = list(universe) if universe is not None else equity_universe()
        if name:
            self.name = name

    def predict(self, data, dates):
        R = data.returns
        cols = list(R.columns)
        uni = [c for c in self.universe if c in cols]
        ui = np.array([cols.index(c) for c in uni])
        fb = cols.index(self.fallback) if self.fallback in cols else None
        cal = data.dates
        vals = R.to_numpy(dtype=np.float64)
        ok = ~np.isnan(vals)
        x = np.where(ok, vals, 0.0)
        lp = np.cumsum(np.log1p(x), axis=0)
        cnt = np.cumsum(ok, axis=0)
        lrf = np.cumsum(np.log1p(data.rf.to_numpy(dtype=np.float64)))

        mkey = cal.year.to_numpy() * 12 + cal.month.to_numpy()
        ms_idx = np.flatnonzero(np.r_[True, mkey[1:] != mkey[:-1]])
        last = int(cal.get_indexer([dates[-1]])[0])
        first = int(cal.get_indexer([dates[0]])[0])
        # tranche events needed: all from roughly one month before the first requested date
        events = sorted((i + off, j) for j, off in enumerate(self.tranche_days) for i in ms_idx
                        if i >= LOOKBACK + 1 and first - 60 <= i + off <= last)

        m = len(cols)
        tranche_w, targets = {}, {}
        for t, j in events:
            mom = lp[t - SKIP] - lp[t - LOOKBACK]
            rf_mom = lrf[t - SKIP] - lrf[t - LOOKBACK]
            valid = (cnt[t] - cnt[t - LOOKBACK] >= 250) & (cnt[t] - cnt[t - 5] >= 5)
            elig = ui[valid[ui]]
            if self.trend_lb:   # absolute trend on a separate (shorter, no-skip) window
                tr_mom = lp[t] - lp[t - self.trend_lb]
                tr_rf = lrf[t] - lrf[t - self.trend_lb]
            else:
                tr_mom, tr_rf = mom, rf_mom
            if self.score == "sharpe":   # momentum per unit of 252-day daily volatility
                sd = x[t - LOOKBACK + 1: t + 1].std(axis=0) * np.sqrt(252) + 1e-12
                sig = (mom - rf_mom) / sd
            else:
                sig = mom
            if len(elig) < 5:
                continue
            k = max(self.k_min, int(round(len(elig) * self.frac)))
            ranked = elig[np.argsort(-sig[elig], kind="stable")]
            picks = []
            if self.max_corr < 1.0:
                win = x[t - LOOKBACK + 1: t + 1]
                C = np.corrcoef(win[:, ranked].T)
                pos = {a: p for p, a in enumerate(ranked)}
                for a in ranked:
                    if all(C[pos[a], pos[b]] <= self.max_corr for b in picks):
                        picks.append(a)
                    if len(picks) == k:
                        break
            else:
                picks = list(ranked[:k])
            kk = len(picks)
            raw = np.arange(kk, 0, -1, dtype=np.float64) if self.rank_weight else np.ones(kk)
            raw /= raw.sum()
            w = np.zeros(m)
            fb_ok = fb is not None and bool(valid[fb]) and tr_mom[fb] > tr_rf
            for a, wa in zip(picks, raw):
                if not self.trend or tr_mom[a] > tr_rf:
                    w[a] += wa
                elif fb_ok:
                    w[fb] += wa
                # else: stays in T-bill cash
            if not self.blend:   # every event recomputes the whole book (no tranche averaging)
                targets[t] = w
                continue
            tranche_w[j] = w
            targets[t] = sum(tranche_w.values()) / len(self.tranche_days) if len(tranche_w) == len(self.tranche_days) \
                else sum(tranche_w.values()) / len(tranche_w)

        out = pd.DataFrame(np.nan, index=dates, columns=cols)
        pos = cal.get_indexer(dates)
        for r, p in enumerate(pos):
            if p in targets:
                out.iloc[r] = targets[p]
        return out
