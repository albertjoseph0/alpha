"""Research grid for momentum portfolio construction (dev-era data only)."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys, json, time
import numpy as np, pandas as pd
from harness import Strategy, run, I49
from harness.data import load


def month_starts(cal, upto):
    cal = cal[cal <= upto]
    m = cal.year * 12 + cal.month
    first = np.r_[True, m[1:] != m[:-1]]
    return cal[first]


class Construct(Strategy):
    refit_every = None

    def __init__(self, frac=1/3, sell=None, weight="eq", K=1, step=1, offset=0, cap=None, volwin=63, day=0, stag=1, gap=5):
        self.stag, self.gap = stag, gap
        self.frac, self.sell, self.weight, self.K, self.step, self.offset, self.cap, self.volwin, self.day = \
            frac, sell, weight, K, step, offset, cap, volwin, day
        self.name = f"c_f{frac:.3f}_s{sell}_{weight}_K{K}_st{step}o{offset}_cap{cap}_v{volwin}"

    def _weights(self, sel, sig, sd):
        k = len(sel)
        if self.weight == "eq":
            w = pd.Series(1.0, index=sel)
        elif self.weight == "rank":        # linear rank among winners: k..1
            w = sig[sel].rank()
        elif self.weight == "invvol":
            w = 1.0 / sd[sel]
        elif self.weight == "kelly":       # mu/sigma^2 with mu = annualised momentum
            w = (sig[sel].clip(lower=0) + 1e-4) / sd[sel] ** 2
        else:
            raise ValueError(self.weight)
        w = w / w.sum()
        if self.cap is not None:
            c = self.cap / k
            for _ in range(20):
                over = w > c + 1e-12
                if not over.any(): break
                excess = (w[over] - c).sum(); w[over] = c
                w[~over] += excess * w[~over] / w[~over].sum()
        return w

    def predict(self, data, dates):
        # research-only speedup: all quantities below are strictly causal (shift/rolling/forward
        # recursion), so targets computed once on the full dev data equal those computed on
        # data.until(d). The final strategy.py runs uncached and passes the harness audit.
        if getattr(self, "_cache", None) is None:
            self._cache = self._compute(CACHE_DATA, CACHE_DATA.dates[CACHE_DATA.dates >= "1929-01-01"])
        return self._cache.reindex(dates)

    def _compute(self, data, dates):
        R = data.tradeable_returns()[I49]
        lp = np.log1p(R.fillna(0)).cumsum()
        mom = lp.shift(21) - lp.shift(252)
        valid = (R.notna().rolling(252).sum() >= 250) & R.notna().rolling(5).sum().ge(5)
        sd = np.log1p(R).rolling(self.volwin, min_periods=self.volwin // 2).std()
        ms = month_starts(data.dates, dates[-1])
        ms = ms[ms >= pd.Timestamp("1927-06-01")]
        if self.day:
            cal = data.dates; ms = cal[np.minimum(cal.get_indexer(ms) + self.day, len(cal) - 1)]
            ms = ms[ms <= dates[-1]]
        cal = data.dates
        ev = [(cal[i], j) for j in range(self.stag)
              for i in np.minimum(cal.get_indexer(ms) + j * self.gap, len(cal) - 1)]
        ev = sorted(e for e in ev if e[0] <= dates[-1])
        held, tranches, targets = [], {}, {}
        for d, j in ev:
            sig = mom.loc[d].where(valid.loc[d]).dropna()
            n = len(sig)
            if n < 5:
                continue
            k = max(1, int(round(n * self.frac)))
            order = sig.sort_values(ascending=False).index
            if self.sell is None:
                sel = list(order[:k])
            else:
                ks = max(k, int(round(n * self.sell)))
                band = set(order[:ks])
                keep = [h for h in held if h in band]
                sel = keep + [a for a in order if a not in keep][: max(0, k - len(keep))]
            held = sel
            midx = d.year * 12 + d.month - 1
            tranches[(midx % self.K, j)] = self._weights(pd.Index(sel), sig, sd.loc[d])
            if (midx - self.offset) % self.step != 0:
                continue
            tw = pd.Series(0.0, index=I49)
            for w in tranches.values():
                tw[w.index] += w.values
            # before all K tranches exist, scale up existing ones
            tw /= tw.sum()
            targets[d] = tw
        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        for d in dates.intersection(pd.DatetimeIndex(list(targets))):
            out.loc[d] = targets[d].values
        return out


WINDOWS = ("dev", "dev_a", "dev_b", "early")

if __name__ == "__main__":
    data = load(until="1999-12-31")
    CACHE_DATA = data
    grid = json.loads(sys.argv[1])
    for cfg in grid:
        t = time.time()
        s = Construct(**cfg)
        res = {w: run(s, window=w, data=data, ledger=False).cagr for w in WINDOWS}
        print(json.dumps(cfg), " ".join(f"{w}={v:+.2%}" for w, v in res.items()), f"({time.time()-t:.0f}s)", flush=True)
        with open(os.path.join(os.path.dirname(__file__), "grid_log.jsonl"), "a") as f:
            f.write(json.dumps({"cfg": cfg, **res}) + "\n")
