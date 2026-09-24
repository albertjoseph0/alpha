"""Portfolio-level DEV analysis (1927-1993 only). French monthly-formed ME x PRIOR portfolios,
trend switch into T-bills, turnover costs. Prints a table; writes dev_portfolio.csv."""
import sys
from common import *

DEV = ("1927-01-01", "1993-12-31")
TO_MOM = float(sys.argv[1]) if len(sys.argv) > 1 else 0.80   # monthly sum|dw| of the winner book
C_MID = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0015  # one-way cost per $ traded

vw = french_25_monthly("vw")
dec = french_10_monthly("vw")
md = market_daily()
mkt_m = monthly(md["Mkt"])
rf_m = monthly(md["RF"])
u = trend_regime_monthly(md["Mkt"]).shift(1)  # signal formed in month t-1 applies to month t
u = u.reindex(mkt_m.index)

cands = {"ME2xP5": vw["ME2 PRIOR5"], "ME3xP5": vw["ME3 PRIOR5"], "ME4xP5": vw["ME4 PRIOR5"],
         "ME1xP5": vw["ME1 PRIOR5"], "ME5xP5": vw["ME5 PRIOR5"], "TopDecile": dec["Hi PRIOR"],
         "Market": mkt_m}


def run(p, switch, to=TO_MOM, c=C_MID, c_def=0.0001):
    p = p.reindex(mkt_m.index)
    df = pd.DataFrame({"p": p, "rf": rf_m, "u": u}).dropna()
    df = df.loc[DEV[0]:DEV[1]]
    if not switch:
        df["u"] = 1.0
    du = df["u"].diff().abs().fillna(0)
    cost = df["u"] * to * c + du * (c + c_def)
    return df["u"] * df["p"] + (1 - df["u"]) * df["rf"] - cost


rows = []
bm = mkt_m.loc[DEV[0]:DEV[1]]
for name, p in cands.items():
    for sw in (False, True):
        for cm in (0, 1, 2):
            to = 0 if name == "Market" else TO_MOM
            r = run(p, sw, to=to, c=C_MID * cm)
            bm = mkt_m.reindex(r.index)
            ex = (r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
                  - bm.groupby(bm.index.year).apply(lambda x: (1 + x).prod() - 1))
            rows.append(dict(port=name, switch=sw, costx=cm, cagr=cagr(r), mkt=cagr(bm),
                             excess=cagr(r) - cagr(bm), maxdd=maxdd(r), vol=r.std() * np.sqrt(12),
                             yrs_beat=(ex > 0).mean()))
T = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(f"DEV {DEV}  TO={TO_MOM}/month  one-way cost={C_MID*1e4:.0f}bp")
print(T.to_string(float_format=lambda x: f"{x:.3f}"))
print("time in offense (mean u):", u.loc[DEV[0]:DEV[1]].mean().round(3))
T.to_csv(OUT / "dev_portfolio.csv", index=False)

# per-subperiod for ME2xP5 switched, base cost
for a, b in (("1927", "1945"), ("1946", "1963"), ("1964", "1979"), ("1980", "1993")):
    r = run(cands["ME2xP5"], True).loc[a:b]
    r0 = run(cands["ME2xP5"], False).loc[a:b]
    print(a, b, f"ME2xP5 sw {cagr(r):.3f} raw {cagr(r0):.3f} mkt {cagr(mkt_m.loc[a:b]):.3f}")

# worst 12-month windows (momentum crashes) in dev, raw vs switched
r0 = run(cands["ME2xP5"], False); r1 = run(cands["ME2xP5"], True)
roll = lambda r: (1 + r).rolling(12).apply(np.prod, raw=True) - 1
w = pd.DataFrame({"raw": roll(r0), "switched": roll(r1), "mkt": roll(mkt_m.reindex(r0.index))})
print("worst 12m windows of raw ME2xP5:"); print(w.nsmallest(5, "raw").round(3).to_string())
print("worst single months raw:", r0.nsmallest(5).round(3).to_dict())
