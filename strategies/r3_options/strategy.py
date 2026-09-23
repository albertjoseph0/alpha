"""r3:options_switch210_mom5_sharpe7 -- trend-switched momentum over the whole ETF universe, with the
option-income (PBP/XYLD/QYLD/JEPI) and low-vol (USMV) funds as ordinary candidates.

  * SPY 210-day (~10-month) total return > 0  -> offense: plain 12-1 momentum, top 5, equal weight
  * otherwise                                  -> defense: Sharpe (12-1 return / 12m vol) momentum,
                                                  top 7, equal weight (in practice bonds, gold,
                                                  defensive sectors; never cash by rule)
  * both sleeves: 4 staggered monthly tranches (trading days 0/5/10/15), VIXY excluded.
The regime is re-read on each tranche day and applied to the whole book.

MomentumSleeve is a helper (not a Strategy); research.py builds all evaluated configurations from it.

Run:   .venv/bin/python -m harness strategies/r3_options/strategy.py --window etf_dev --benchmarks
Live:  .venv/bin/python -m harness.live strategies/r3_options/strategy.py --capital 100000
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

from harness import MarketData, Strategy

LOOKBACK, SKIP = 252, 21


def month_offsets(cal: pd.DatetimeIndex) -> np.ndarray:
    """Trading-day index within the calendar month (0 = first trading day). Causal: it depends
    only on dates up to and including each date."""
    m = np.asarray(cal.year * 12 + cal.month)
    new = np.r_[True, m[1:] != m[:-1]]
    start = np.maximum.accumulate(np.where(new, np.arange(len(cal)), 0))
    return np.arange(len(cal)) - start


class MomentumSleeve:
    """score  'sharpe': 12-1 month log return / annualised daily vol over the same year
                        (risk-adjusted 'smooth trend' momentum)
              'mom'   : plain 12-1 month log return
    k       : holdings, equal weight ('eq') or inverse 63-day vol ('invvol')
    tranches: trading-day offsets within the month; each tranche is refreshed monthly and the book
              is their equal average
    exclude : tickers never held (VIXY by default: a decaying hedge, never a trend asset)"""
    def __init__(self, score="sharpe", k=7, weight="eq", tranches=(0, 5, 10, 15), exclude=("VIXY",)):
        self.score, self.k, self.weight = score, k, weight
        self.tranches, self.exclude = tuple(tranches), tuple(exclude)

    def _targets(self, R: pd.DataFrame, when: pd.DatetimeIndex) -> pd.DataFrame:
        lr = np.log1p(R)
        lp = lr.fillna(0.0).cumsum()
        mom = lp.shift(SKIP) - lp.shift(LOOKBACK)
        ok = (R.notna().rolling(LOOKBACK).sum() >= LOOKBACK - 2) & (R.notna().rolling(5).sum() == 5)
        if self.score == "sharpe":
            vol = lr.rolling(LOOKBACK, min_periods=LOOKBACK - 2).std() * np.sqrt(252)
            sc = mom / vol.clip(lower=0.02)
        else:
            sc = mom
        vol63 = lr.rolling(63, min_periods=60).std() * np.sqrt(252)
        cols = [c for c in R.columns if c not in self.exclude]
        out = pd.DataFrame(np.nan, index=when, columns=R.columns)
        for d in when:
            s = sc.loc[d, cols].where(ok.loc[d, cols]).dropna()
            if len(s) < self.k:
                continue
            top = s.nlargest(self.k).index
            out.loc[d] = 0.0
            if self.weight == "invvol":
                iv = 1.0 / vol63.loc[d, top].clip(lower=0.02)
                out.loc[d, top] = (iv / iv.sum()).values
            else:
                out.loc[d, top] = 1.0 / self.k
        return out

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        R = data.returns
        cal = data.dates
        off = month_offsets(cal)
        pos = cal.get_indexer(dates)
        out = pd.DataFrame(np.nan, index=dates, columns=R.columns)
        is_ref = np.isin(off[pos], self.tranches)
        if not is_ref.any():
            return out
        # for each refresh date, the latest date <= it on which each tranche was refreshed
        last = {}
        for p in pos[is_ref]:
            lst = []
            for o in self.tranches:
                q = p
                while q >= 0 and off[q] != o:
                    q -= 1
                if q >= 0:
                    lst.append(q)
            last[cal[p]] = cal[lst]
        need = pd.DatetimeIndex(sorted(set().union(*[set(v) for v in last.values()])))
        tg = self._targets(R, need)
        for d, lst in last.items():
            w = tg.loc[lst].dropna(how="all")
            if not w.empty:
                out.loc[d] = w.mean().values
        return out


class TrendSwitchMomentum(Strategy):
    name = "r3:options_switch210_mom5_sharpe7"
    refit_every = None
    TREND_ASSET, TREND_LEN = "SPY", 210

    def __init__(self):
        self.offense = MomentumSleeve("mom", 5, "eq", (0, 5, 10, 15), ("VIXY",))
        self.defense = MomentumSleeve("sharpe", 7, "eq", (0, 5, 10, 15), ("VIXY",))

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        w_on = self.offense.predict(data, dates)
        w_off = self.defense.predict(data, dates)
        lp = np.log1p(data.returns[self.TREND_ASSET].fillna(0.0)).cumsum()
        up = ((lp - lp.shift(self.TREND_LEN)) > 0).loc[dates].values.astype(float)
        return w_on.mul(up, axis=0) + w_off.mul(1.0 - up, axis=0)
