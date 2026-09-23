"""Check estimator bias/dispersion on synthetic series of the sizes used later."""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hurst import rs_hurst, dfa_hurst, vt_hurst, lo_hurst, lo_v


def fgn(n, H, rng):
    # Davies-Harte exact fGn
    k = np.arange(0, n)
    g = 0.5 * (np.abs(k - 1) ** (2 * H) - 2 * np.abs(k) ** (2 * H) + np.abs(k + 1) ** (2 * H))
    c = np.concatenate([g, g[-2:0:-1]])
    lam = np.fft.fft(c).real
    lam[lam < 0] = 0
    m = len(c)
    z = rng.standard_normal(m) + 1j * rng.standard_normal(m)
    w = np.fft.fft(np.sqrt(lam / (2 * m)) * z)
    return w.real[:n]


rng = np.random.default_rng(0)
N = 260
sc_rs = [8, 13, 26, 52, 65, 130]
sc_dfa = [8, 13, 26, 52]
sc_vt = [2, 4, 8, 13, 26]
cases = {"iid": lambda: rng.standard_normal(N), "ar1_0.2": None,
         "fgn0.6": lambda: fgn(N, 0.6, rng), "fgn0.7": lambda: fgn(N, 0.7, rng),
         "fgn0.4": lambda: fgn(N, 0.4, rng), "t3_iid": lambda: rng.standard_t(3, N)}


def ar1():
    e = rng.standard_normal(N + 50)
    x = np.zeros_like(e)
    for i in range(1, len(e)):
        x[i] = 0.2 * x[i - 1] + e[i]
    return x[50:]


cases["ar1_0.2"] = ar1
for name, gen in cases.items():
    res = {k: [] for k in ["rs", "dfa", "vt", "lo2"]}
    for _ in range(300):
        x = gen()
        res["rs"].append(rs_hurst(x, sc_rs))
        res["dfa"].append(dfa_hurst(x, sc_dfa))
        res["vt"].append(vt_hurst(x, sc_vt))
        res["lo2"].append(lo_hurst(x, 2))
    print(f"{name:9s} " + "  ".join(f"{k}: {np.nanmean(v):.3f}±{np.nanstd(v):.3f}" for k, v in res.items()))
