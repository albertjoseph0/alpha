"""DEV-period study (2018-01-01 .. 2021-12-31). Never touches 2022+ data (backtest.run truncates at `end`).

Canonical rule declared BEFORE any backtest was run: lookback 28d, top 5, universe top-30 by
30d mean quote volume, min age 60d, BTC > SMA100 filter, weekly (Sun signal, Mon close trade).
"""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5/m02_crypto_momentum")
import backtest as bt

S, E = "2018-01-01", "2021-12-31"
pd.set_option("display.width", 200)


def line(name, eq):
    s = bt.stats(eq)
    return dict(name=name, cagr=round(100 * s["cagr"], 1), maxdd=round(100 * s["maxdd"], 1),
                sharpe=round(s["sharpe"], 2))


def yearly(eq):
    y = eq.resample("YE").last()
    y = pd.concat([pd.Series([eq.iloc[0]], index=[eq.index[0] - pd.Timedelta(days=1)]), y])
    return (y.pct_change().dropna() * 100).round(1)


def main():
    rows, curves = [], {}
    btc = bt.bench_btc(S, E); spy = bt.bench_spy(S, E)
    rows.append(line("BTC buy&hold", btc)); curves["BTC"] = btc
    rows.append(line("SPY buy&hold", spy)); curves["SPY"] = spy
    configs = {
        "CANONICAL mom L28 K5 SMA100": {},
        "  2x costs": dict(cost_mult=2.0),
        "  delisted -> zero": dict(delist="zero"),
        "  no BTC filter": dict(btc_sma=0),
        "BTC w/ same SMA100 filter": dict(mode="btc"),
        "EW top-30 w/ SMA100 filter": dict(mode="ew_univ"),
        "EW top-30 no filter": dict(mode="ew_univ", btc_sma=0),
        "  liq rank = median qv": dict(liq_stat="median"),
        "  liq rank = trade count": dict(liq_stat="trades"),
        "  min age 180d": dict(min_age=180),
        "  daily rebalance": dict(rebal="D"),
        "  universe top-20": dict(n_univ=20),
        "  universe top-50": dict(n_univ=50),
    }
    info = {}
    for name, kw in configs.items():
        eq, inf = bt.run(S, E, **kw)
        curves[name] = eq; info[name] = inf
        r = line(name, eq)
        r["trades"] = inf["n_trades"]
        r["ann_turnover"] = round(np.sum(inf["turnover"]) / bt.stats(eq)["years"], 1)
        r["delist_hits"] = len(inf["delist"])
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nCalendar-year returns (%)")
    yr = pd.DataFrame({k: yearly(curves[k]) for k in ["BTC", "SPY", "CANONICAL mom L28 K5 SMA100",
                                                      "BTC w/ same SMA100 filter", "EW top-30 w/ SMA100 filter"]})
    print(yr.to_string())

    print("\nSub-period 2018-2020 (ex-2021 mania)")
    sub = []
    for name, eq in [("BTC", bt.bench_btc(S, "2020-12-31")), ("SPY", bt.bench_spy(S, "2020-12-31"))]:
        sub.append(line(name, eq))
    for name, kw in [("canonical", {}), ("canonical 2x", dict(cost_mult=2)),
                     ("BTC+filter", dict(mode="btc")), ("EW30+filter", dict(mode="ew_univ"))]:
        sub.append(line(name, bt.run(S, "2020-12-31", **kw)[0]))
    print(pd.DataFrame(sub).to_string(index=False))

    # contribution of top single trades: which coins drove it
    inf = info["CANONICAL mom L28 K5 SMA100"]
    held = pd.Series([s for w in inf["targets"].values() for s in w.index]).value_counts()
    print("\nMost-held instruments (weeks):", held.head(15).to_dict())
    print("Delisting events while held:", inf["delist"])
    n_univ = [len(w) for w in bt.run(S, E, mode="ew_univ")[1]["targets"].values() if len(w)]
    print("Universe size over dev: min %d median %d max %d" % (min(n_univ), np.median(n_univ), max(n_univ)))
    on = np.mean([len(w) > 0 for w in inf["targets"].values()])
    print("Fraction of weeks invested (BTC filter on): %.2f" % on)

    print("\nParameter grid (lookback x top_k x btc_sma), dev CAGR %, 1x costs")
    g = []
    for L, K, sma in itertools.product([7, 14, 28, 56, 90], [3, 5, 10], [0, 50, 100, 200]):
        eq, _ = bt.run(S, E, lookback=L, top_k=K, btc_sma=sma)
        s = bt.stats(eq)
        g.append(dict(L=L, K=K, sma=sma, cagr=round(100 * s["cagr"], 1), maxdd=round(100 * s["maxdd"], 1)))
    g = pd.DataFrame(g)
    print(g.pivot_table(index=["sma", "K"], columns="L", values="cagr").to_string())
    g.to_csv("/home/user/alpha/research/round5/m02_crypto_momentum/dev_grid.csv", index=False)
    print("grid median CAGR %.1f, share of cells beating BTC by 20pts: %.2f" %
          (g.cagr.median(), np.mean(g.cagr > rows[0]["cagr"] + 20)))

    print("\nCapacity (dev, canonical, sqrt impact Y=1*sigma_d*sqrt(order/ADV))")
    cap = []
    for aum in [1e5, 1e6, 1e7, 3e7, 1e8, 3e8]:
        eq, _ = bt.run(S, E, aum=aum)
        cap.append(dict(aum=f"${aum:,.0f}", cagr=round(100 * bt.stats(eq)["cagr"], 1)))
    print(pd.DataFrame(cap).to_string(index=False))


if __name__ == "__main__":
    main()
