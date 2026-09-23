"""Evaluate one named config on etf_dev, etf_dev_a, etf_dev_b; append to evals.log."""
import os, sys, json
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, "/home/user/alpha"); sys.path.insert(0, os.path.dirname(__file__))
import harness
from xasset import XAsset
LOG = os.path.join(os.path.dirname(__file__), "evals.log")
data = harness.load_etf_dev()
for arg in sys.argv[1:]:
    tag, kw = arg.split("=", 1)
    kw = eval(f"dict({kw})")
    res = {w: harness.run(XAsset(**kw), window=w, data=data, ledger=False).cagr for w in ("etf_dev", "etf_dev_a", "etf_dev_b")}
    line = f"{tag}\t{json.dumps(kw)}\tdev={res['etf_dev']:.2%}\tdev_a={res['etf_dev_a']:.2%}\tdev_b={res['etf_dev_b']:.2%}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")
