"""Stock-level DEV (holding months 2012-01 .. 2018-12 ONLY). Usage: stock_dev.py [src ...]
Writes stock_dev_summary.csv (appends per src) and books/<src>_N<k>_<scen>_dev.csv."""
import sys
from stock_bt import *

DEV = ("2012-01", "2018-12")
C1 = 0.0015                       # one-way cost per $ traded, 1x (2x = 30bp)
SRCS = sys.argv[1:] or ["chg"]
BK = OUT / "books"
BK.mkdir(exist_ok=True)
rows = []
for src in SRCS:
    for N in (5, 10):
        for scen in ("drop", "neutral", "x50", "x100", "m50", "m100"):
            b = build_book(N, scen, *DEV, src=src)
            b.to_csv(BK / f"{src}_N{N}_{scen}_dev.csv")
            for cm in (1, 2):
                for sw in (False, True):
                    r = net(b, C1 * cm, switch=sw, cost_mult_def=cm)
                    for bn in ("spy", "ijh"):
                        rows.append(summary(r, b[bn], f"top{N}", src=src, scen=scen, costx=cm, switch=sw,
                                            vs=bn, to=b["to"].mean(), miss=(b.n_miss / b.n_mem).mean()))
        print(src, N, "done", flush=True)
    # concentration within the same universe (drop / neutral, 1x, no switch)
    for N in (5, 10, 20, 40, 80):
        for scen in ("drop", "neutral"):
            b = build_book(N, scen, *DEV, src=src)
            r = net(b, C1)
            rows.append(summary(r, b["spy"], f"top{N}", src=src, scen=scen, costx=1, switch=False, vs="spy",
                                to=b["to"].mean(), miss=(b.n_miss / b.n_mem).mean()))
    b = build_book(10, "drop", *DEV, src=src)
    for nm in ("uni", "q5", "ijh"):
        rows.append(summary(b[nm], b["spy"], nm, src=src, scen="drop", costx=0, switch=False, vs="spy"))
T = pd.DataFrame(rows)
f = OUT / "stock_dev_summary.csv"
if f.exists():
    old = pd.read_csv(f)
    T = pd.concat([old[~old.src.isin(SRCS)], T])
T.to_csv(f, index=False)
pd.set_option("display.width", 250)
show = T[(T.vs == "spy") & T.src.isin(SRCS)]
print(show.to_string(float_format=lambda x: f"{x:.3f}"))
