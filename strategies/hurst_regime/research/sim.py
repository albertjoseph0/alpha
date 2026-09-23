"""Research scorer: harness.engine.simulate on load_dev() data (identical frictions).
Every call to score() is logged to research/eval_log.txt to keep an honest count."""
from common import *  # noqa
from harness.engine import simulate
from harness import WINDOWS

D = load_dev()
LOG = os.path.join(HERE, "eval_log.txt")


def score(W: pd.DataFrame, label: str, windows=("dev", "dev_a", "dev_b"), log=True):
    out = {}
    for w in windows:
        s, e = WINDOWS[w]
        out[w] = simulate(W, D, s, e).cagr
    if log:
        with open(LOG, "a") as f:
            f.write(f"{label}\t" + "\t".join(f"{k}={v:+.4f}" for k, v in out.items()) + "\n")
    return out


def fmt(label, out, extra=""):
    return f"{label:55s} " + "  ".join(f"{k} {v:+.2%}" for k, v in out.items()) + (f"  {extra}" if extra else "")


def turnover(W):
    return float(W.fillna(0).diff().abs().sum(axis=1).mean() * 252)
