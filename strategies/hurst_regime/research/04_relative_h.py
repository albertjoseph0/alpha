"""H of RELATIVE returns (industry - market): is cross-sectional persistence real?
And does per-industry H (rolling) improve XS-momentum selection?"""
from common import *  # noqa
from hurst import rs_hurst, dfa_hurst, vt_hurst, lo_v

d, lr = get()
rel = lr[:, 1:] - lr[:, [0]]           # 12 industries relative to Mkt
IND = ASSETS[1:]
wk = block_sums(rel, 5)
mo = block_sums(rel, 21)
rng = np.random.default_rng(2)
print("Full-sample H of relative returns: weekly [RS, DFA, VT] vs shuffle 97.5%; monthly VT; Lo V(q=4 weekly)")
for j, a in enumerate(IND):
    x = wk[:, j]
    h = [rs_hurst(x, [16, 32, 64, 128, 256, 512]), dfa_hurst(x, [8, 16, 32, 64, 128, 256]), vt_hurst(x, [2, 4, 8, 16, 32, 64])]
    sh = np.array([[rs_hurst(p, [16, 32, 64, 128, 256, 512]), dfa_hurst(p, [8, 16, 32, 64, 128, 256]), vt_hurst(p, [2, 4, 8, 16, 32, 64])]
                   for p in (rng.permutation(x) for _ in range(40))])
    hm = vt_hurst(mo[:, j], [2, 3, 6, 12, 24])
    print(f"{a:6s} RS {h[0]:.3f}({np.percentile(sh[:,0],97.5):.3f}) DFA {h[1]:.3f}({np.percentile(sh[:,1],97.5):.3f}) "
          f"VT {h[2]:.3f}({np.percentile(sh[:,2],97.5):.3f}) | monthly VT {hm:.3f} | LoV {lo_v(x, 4):.2f} "
          f"| ac1 wk {np.corrcoef(x[1:], x[:-1])[0,1]:+.3f} mo {np.corrcoef(mo[1:, j], mo[:-1, j])[0,1]:+.3f}")
