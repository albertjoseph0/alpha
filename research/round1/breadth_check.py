"""Plain 12-1 momentum, monthly, equal-weight top third: 12 vs 49 industries (dev-era data only)."""
import numpy as np, pandas as pd
from harness import Strategy, run, INDUSTRIES, I49
from harness.data import load

class Mom(Strategy):
    refit_every = None
    def __init__(self, cols, frac): self.cols, self.frac = cols, frac; self.name = f"mom_{len(cols)}_{frac}"
    def predict(self, data, dates):
        R = data.tradeable_returns()[self.cols]
        lp = np.log1p(R.fillna(0)).cumsum()
        mom = (lp.shift(21) - lp.shift(252))
        valid = R.notna().rolling(252).sum() >= 250           # enough history
        cal = data.dates; pos = cal.get_indexer(dates)
        first = dates.month != np.where(pos > 0, cal[np.maximum(pos-1,0)].month, -1)
        out = pd.DataFrame(np.nan, index=dates, columns=self.cols)
        for d in dates[first]:
            m = mom.loc[d].where(valid.loc[d]).dropna()
            k = max(1, int(round(len(m) * self.frac)))
            top = m.nlargest(k).index
            out.loc[d] = 0.0; out.loc[d, top] = 1.0 / k
        return out

data = load(until="1999-12-31")
for cols in (INDUSTRIES, I49):
    for frac in (1/3, 1/5, 1/10):
        s = Mom(cols, frac)
        print(s.name, *(f"{w}={run(s, window=w, data=data, ledger=False).cagr:+.2%}" for w in ("dev","dev_a","dev_b","early")))
