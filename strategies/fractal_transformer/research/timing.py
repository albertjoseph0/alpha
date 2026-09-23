import os, sys, time
os.environ["OMP_NUM_THREADS"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, torch
torch.set_num_threads(1)
import ft_sim, ft_model as fm
t0 = time.time(); R = ft_sim.generate(0, 256, 4000); t1 = time.time()
C = fm.Corpus(R); t2 = time.time()
P, N = R.shape
tt = np.arange(1000, N - 2 - 63)
ip = np.repeat(np.arange(P), len(tt)); it = np.tile(tt, P)
torch.manual_seed(0); m = fm.VolTransformer()
print("params", sum(p.numel() for p in m.parameters()))
t3 = time.time(); l = fm.train(m, C, ip, it, 200, 1e-3, 0); t4 = time.time()
print(f"gen {t1-t0:.1f}s corpus {t2-t1:.1f}s train200 {t4-t3:.1f}s loss {l:.4f}")
