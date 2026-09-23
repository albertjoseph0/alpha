"""Rolling H of signed and absolute weekly returns per asset; shuffle-test significance."""
from common import *  # noqa
from hurst import rs_hurst, dfa_hurst, vt_hurst, lo_v

d, lr = get()
wk = block_sums(lr, 5)                        # weekly log returns, anchored
dates = d.dates[4::5][: len(wk)]
W = 260
sc_rs, sc_dfa, sc_vt = [8, 13, 26, 52, 65, 130], [8, 13, 26, 52], [2, 4, 8, 13, 26]
rng = np.random.default_rng(1)

print("Full-sample (1926-99) H on weekly returns; shuffled-surrogate 95% band in brackets")
for j, a in enumerate(ASSETS):
    x = wk[:, j]
    h = (rs_hurst(x, [16, 32, 64, 128, 256, 512]), dfa_hurst(x, [8, 16, 32, 64, 128, 256]),
         vt_hurst(x, [2, 4, 8, 16, 32, 64]))
    sh = np.array([[rs_hurst(p, [16, 32, 64, 128, 256, 512]), dfa_hurst(p, [8, 16, 32, 64, 128, 256]),
                    vt_hurst(p, [2, 4, 8, 16, 32, 64])] for p in (rng.permutation(x) for _ in range(60))])
    ha = (rs_hurst(np.abs(x), [16, 32, 64, 128, 256, 512]), dfa_hurst(np.abs(x), [8, 16, 32, 64, 128, 256]))
    lo = lo_v(x, 8)
    print(f"{a:6s} RS {h[0]:.3f} [{np.percentile(sh[:,0],2.5):.3f},{np.percentile(sh[:,0],97.5):.3f}]"
          f"  DFA {h[1]:.3f} [{np.percentile(sh[:,1],2.5):.3f},{np.percentile(sh[:,1],97.5):.3f}]"
          f"  VT {h[2]:.3f} [{np.percentile(sh[:,2],2.5):.3f},{np.percentile(sh[:,2],97.5):.3f}]"
          f"  | Lo V8 {lo:.2f}  | |r|: RS {ha[0]:.2f} DFA {ha[1]:.2f}")

# rolling (5y window, every 4 weeks)
rows = []
for t in range(W, len(wk) + 1, 4):
    x = wk[t - W:t]
    for j, a in enumerate(ASSETS):
        rows.append((dates[t - 1], a, rs_hurst(x[:, j], sc_rs), dfa_hurst(x[:, j], sc_dfa),
                     vt_hurst(x[:, j], sc_vt), lo_v(x[:, j], 4), dfa_hurst(np.abs(x[:, j]), sc_dfa)))
H = pd.DataFrame(rows, columns=["date", "asset", "rs", "dfa", "vt", "loV", "dfa_abs"])
H.to_pickle(os.path.join(HERE, "h_weekly_5y.pkl"))
print("\nRolling 5y-weekly H, Mkt, by decade (mean):")
m = H[H.asset == "Mkt"].set_index("date")
print(m.groupby(m.index.year // 10 * 10)[["rs", "dfa", "vt", "loV", "dfa_abs"]].mean().round(3))
print("\nAll assets pooled: mean/sd", H[["rs", "dfa", "vt", "dfa_abs"]].agg(["mean", "std"]).round(3).to_dict())
print("corr between estimators (pooled):\n", H[["rs", "dfa", "vt", "loV", "dfa_abs"]].corr().round(2))
