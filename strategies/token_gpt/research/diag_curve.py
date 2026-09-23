"""Learning-curve diagnostic on PRE-DEV data only (train <= 1944, validate 1945-49).

Used to choose the training budget (steps) and model size without looking at 1950-99.
Usage: python diag_curve.py [steps] [d] [n_layer] [L] [h]
"""
import os
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, "/home/user/alpha")
import numpy as np
import torch

import gpt_core as G
from harness import load_dev

steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
d = int(sys.argv[2]) if len(sys.argv) > 2 else 32
nl = int(sys.argv[3]) if len(sys.argv) > 3 else 2
L = int(sys.argv[4]) if len(sys.argv) > 4 else 64
h = int(sys.argv[5]) if len(sys.argv) > 5 else 5
K = 16

data = load_dev()
dates = data.dates
x = (np.log1p(data.returns.to_numpy()) - np.log1p(data.rf.to_numpy())[:, None])
x = x[dates <= "1949-12-31"]
dts = dates[dates <= "1949-12-31"]
z_in, _, _ = G.make_z(x, h)
t_tr_end = int(np.searchsorted(dts, np.datetime64("1944-12-31"), side="right")) - 1
zz = z_in[:t_tr_end + 1]
edges = np.quantile(zz[np.isfinite(zz)], np.linspace(0, 1, K + 1)[1:-1])
print("edges", np.round(edges, 2))
c = G.Corpus(x, 0, h, edges)
assets = list(range(13))
# baseline CE: unconditional frequencies on train targets
yt = c.tok_out[:t_tr_end - h - 1]
freq = np.bincount(yt[yt >= 0].ravel(), minlength=K) / (yt >= 0).sum()
t_va0 = t_tr_end + 1
t_va1 = len(dts) - h - 2
yv = []
for a in assets:
    e = G.valid_ends(c, L, a, t_va1)
    e = e[e >= t_va0][::h]
    yv.append(c.tok_out[e, a])
yv = np.concatenate(yv)
print("baseline CE val (train freq):", -np.mean(np.log(freq[yv])), " uniform:", np.log(K))

torch.manual_seed(0)
m = G.TinyGPT(K, L, d=d, n_layer=nl, n_head=2, d_ff=2 * d)
print("params", sum(p.numel() for p in m.parameters()))
t0 = time.time()
hist = G.train(m, c, assets, t_tr_end - h - 1, steps, seed=0, log_every=max(1, steps // 10),
               val=(assets, t_va0, t_va1))
print("time %.1fs" % (time.time() - t0))
for r in hist:
    print(r)
