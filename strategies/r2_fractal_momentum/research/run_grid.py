import os, sys, time
os.environ["OMP_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from signals import signal, xs_rank
from harness import Strategy, run, I49
from harness.data import load


class SigMom(Strategy):
    refit_every = None

    def __init__(self, spec, frac=1/3):
        self.spec, self.frac = spec, frac
        self.name = "r:" + "+".join(spec)

    def predict(self, data, dates):
        R = data.tradeable_returns()[I49]
        valid = (R.notna().rolling(252).sum() >= 250).to_numpy()
        r = np.log1p(R.fillna(0).to_numpy(np.float64))
        if len(self.spec) == 1:
            s = signal(self.spec[0], r)
        else:
            s = np.nanmean([xs_rank(np.where(valid, signal(k, r), np.nan)) for k in self.spec], axis=0)
        s = np.where(valid, s, np.nan)
        cal = data.dates; pos = cal.get_indexer(dates)
        first = dates.month != np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        for i in np.where(first)[0]:
            row = pd.Series(s[pos[i]], index=I49).dropna()
            k = max(1, int(round(len(row) * self.frac)))
            out.iloc[i] = 0.0
            out.loc[dates[i], row.nlargest(k).index] = 1.0 / k
        return out


if __name__ == "__main__":
    data = load(until="1999-12-31")
    for arg in sys.argv[1:]:
        spec = arg.split("+")
        t = time.time()
        res = [run(SigMom(spec), window=w, data=data, ledger=False).cagr for w in ("dev", "dev_a", "dev_b", "early")]
        line = f"{arg:22s} " + " ".join(f"{x:+.2%}" for x in res) + f"  ({time.time()-t:.0f}s)"
        print(line, flush=True)
        with open(os.path.join(os.path.dirname(__file__), "evals.log"), "a") as f:
            f.write(line + "\n")
