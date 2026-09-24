"""French DEV (1927-1993 only): choose the final portfolio-level configuration.
Subperiod consistency of ME2/ME3/ME4 x PRIOR5 with/without the trend switch, and an accounting of
what the switch costs (bull-market lag) vs what it saves (bear markets / momentum crashes).
Reuses run() from dev_portfolio.py logic (T-bill defense, 1-month-lagged trend ensemble,
TO=0.80 sum|dw| per month, 15bp one-way). Writes french_dev_select.csv."""
from common import *

DEV = ("1927-01-01", "1993-12-31")
TO, C1 = 0.80, 0.0015
vw = french_25_monthly("vw")
md = market_daily()
mkt_m, rf_m = monthly(md["Mkt"]), monthly(md["RF"])
u = trend_regime_monthly(md["Mkt"]).shift(1).reindex(mkt_m.index)


def run(p, switch, c=C1, to=TO, c_def=0.0001):
    df = pd.DataFrame({"p": p.reindex(mkt_m.index), "rf": rf_m, "u": u}).dropna().loc[DEV[0]:DEV[1]]
    if not switch:
        df["u"] = 1.0
    du = df["u"].diff().abs().fillna(0)
    return df["u"] * df["p"] + (1 - df["u"]) * df["rf"] - (df["u"] * to * c + du * (c + c_def))


SUB = (("1927", "1945"), ("1946", "1963"), ("1964", "1979"), ("1980", "1993"))
rows = []
for b in ("ME2", "ME3", "ME4"):
    for sw in (False, True):
        for cm in (1, 2):
            r = run(vw[f"{b} PRIOR5"], sw, c=C1 * cm)
            m = mkt_m.reindex(r.index)
            d = dict(port=f"{b}xP5", switch=sw, costx=cm, cagr=cagr(r), excess=cagr(r) - cagr(m),
                     maxdd=maxdd(r), vol=r.std() * np.sqrt(12),
                     sharpe=((r - rf_m.reindex(r.index)).mean() / r.std()) * np.sqrt(12))
            for a, z in SUB:
                d[f"ex_{a}_{z}"] = cagr(r.loc[a:z]) - cagr(m.loc[a:z])
            rows.append(d)
T = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(T.to_string(float_format=lambda x: f"{x:.3f}"))
T.to_csv(OUT / "french_dev_select.csv", index=False)

# what the switch costs vs saves (ME3, 1x): months in defense split by market direction
r0, r1 = run(vw["ME3 PRIOR5"], False), run(vw["ME3 PRIOR5"], True)
diff = np.log1p(r1) - np.log1p(r0)
m = mkt_m.reindex(r0.index)
uu = u.reindex(r0.index)
yrs = len(r0) / 12
print("\nSwitch accounting, ME3xP5 1x, DEV (log-return pts per year of the whole period):")
print(f"  total effect {diff.sum() / yrs * 100:+.2f}/yr; months with u<1: {(uu < 1).mean():.2f}; "
      f"fully out (u=0): {(uu == 0).mean():.2f}")
print(f"  in months when market fell: {diff[m < 0].sum() / yrs * 100:+.2f}/yr ; when market rose: "
      f"{diff[m >= 0].sum() / yrs * 100:+.2f}/yr")
roll = lambda r: (1 + r).rolling(12).apply(np.prod, raw=True) - 1
print(f"  worst 12m: raw {roll(r0).min():.3f}, switched {roll(r1).min():.3f}; max DD raw {maxdd(r0):.3f} "
      f"switched {maxdd(r1):.3f}")
for a, z in (("1929-09", "1932-06"), ("1932-07", "1933-12"), ("1937-03", "1938-03"), ("1973-01", "1974-12"),
             ("1987-08", "1987-12")):
    print(f"  {a}..{z}: raw {(1 + r0.loc[a:z]).prod() - 1:+.3f} switched {(1 + r1.loc[a:z]).prod() - 1:+.3f} "
          f"mkt {(1 + m.loc[a:z]).prod() - 1:+.3f}")
