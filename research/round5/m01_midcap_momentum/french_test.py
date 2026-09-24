"""Pre-registered French TEST run (see PREREG.md). Runs DEV (as a reproduction check) and TEST
1994-01..2026-07 ONCE. Writes french_test.csv (summary) and french_test_yearly.csv (yearly returns)."""
from common import *

PER = {"DEV": ("1927-01-01", "1993-12-31"), "TEST": ("1994-01-01", "2026-12-31")}
TO, C1 = 0.80, 0.0015
vw = french_25_monthly("vw")
n = french_25_monthly("n")
sz = french_25_monthly("size")
md = market_daily()
mkt_m, rf_m = monthly(md["Mkt"]), monthly(md["RF"])
u = trend_regime_monthly(md["Mkt"]).shift(1).reindex(mkt_m.index)
me3_cols = [f"ME3 PRIOR{k}" for k in range(1, 6)]
w = (n[me3_cols] * sz[me3_cols]).values
me3 = pd.Series((vw[me3_cols].values * w).sum(1) / w.sum(1), index=vw.index)  # ME3 size quintile, VW


def run(p, switch, c, a, b, to=TO, c_def=0.0001):
    df = pd.DataFrame({"p": p.reindex(mkt_m.index), "rf": rf_m, "u": u}).dropna().loc[a:b]
    if not switch:
        df["u"] = 1.0
    du = df["u"].diff().abs().fillna(0)
    return df["u"] * df["p"] + (1 - df["u"]) * df["rf"] - (df["u"] * to * c + du * (c + c_def))


yr = lambda r: r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
rows, yearly = [], {}
for per, (a, b) in PER.items():
    m = mkt_m.loc[a:b]
    m3 = me3.reindex(m.index)
    yearly[f"{per}_mkt"] = yr(m)
    yearly[f"{per}_me3"] = yr(m3)
    for sw in (False, True):
        for cm in (1, 2):
            r = run(vw["ME3 PRIOR5"], sw, C1 * cm, a, b)
            mm = mkt_m.reindex(r.index)
            ex_y = yr(r) - yr(mm)
            rows.append(dict(period=per, strat="ME3xP5" + ("+switch" if sw else ""), costx=cm,
                             start=r.index[0].strftime("%Y-%m"), end=r.index[-1].strftime("%Y-%m"),
                             cagr=cagr(r), mkt=cagr(mm), excess=cagr(r) - cagr(mm),
                             me3=cagr(m3.reindex(r.index)), excess_vs_me3=cagr(r) - cagr(m3.reindex(r.index)),
                             maxdd=maxdd(r), mkt_maxdd=maxdd(mm), vol=r.std() * np.sqrt(12),
                             yrs_beat=(ex_y > 0).mean(), n_years=len(ex_y)))
            if cm == 1:
                yearly[f"{per}_" + ("sw" if sw else "raw")] = yr(r)
T = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(T.to_string(float_format=lambda x: f"{x:.3f}"))
T.to_csv(OUT / "french_test.csv", index=False)
Y = pd.DataFrame(yearly)
Y.to_csv(OUT / "french_test_yearly.csv")
t = Y[["TEST_raw", "TEST_sw", "TEST_mkt", "TEST_me3"]].dropna()
t["ex_raw"], t["ex_sw"] = t.TEST_raw - t.TEST_mkt, t.TEST_sw - t.TEST_mkt
print("\nTEST yearly (1x costs):")
print(t.round(3).to_string())
# subperiods of TEST
for a, b in (("1994", "2001"), ("2002", "2009"), ("2010", "2017"), ("2018", "2026")):
    r = run(vw["ME3 PRIOR5"], False, C1, a, b + "-12-31")
    r1 = run(vw["ME3 PRIOR5"], True, C1, a, b + "-12-31")
    mm = mkt_m.reindex(r.index)
    print(f"{a}-{b}: raw {cagr(r):.3f} sw {cagr(r1):.3f} mkt {cagr(mm):.3f} me3 {cagr(me3.reindex(r.index)):.3f}")
