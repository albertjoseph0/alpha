"""SEALED TEST (2022-01-01 .. data end). Run ONCE, only after PREREG.md is written.
Frozen rule = canonical DEFAULT in backtest.py (lookback 28, top 5, top-30 universe by 30d mean
quote volume, min age 60d, BTC > SMA100, weekly Sun signal -> Mon close trade)."""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5/m02_crypto_momentum")
import backtest as bt

OUT = "/home/user/alpha/research/round5/m02_crypto_momentum"
S = "2022-01-01"
pd.set_option("display.width", 200)


def main():
    close, _, _ = bt.load()
    E = str(close["BTCUSDT"].dropna().index[-1].date())
    print("TEST period", S, "->", E)
    rows, curves = [], {}

    def add(name, eq, inf=None):
        s = bt.stats(eq)
        r = dict(name=name, cagr=round(100 * s["cagr"], 1), maxdd=round(100 * s["maxdd"], 1),
                 sharpe=round(s["sharpe"], 2))
        if inf is not None:
            r["trades"] = inf["n_trades"]
            r["delist_hits"] = len(inf["delist"])
        rows.append(r); curves[name] = eq

    add("BTC buy&hold", bt.bench_btc(S, E))
    add("SPY buy&hold", bt.bench_spy(S, E))
    for name, kw in [("CANONICAL (delist->last)", {}), ("CANONICAL 2x costs", dict(cost_mult=2.0)),
                     ("CANONICAL delist->zero", dict(delist="zero")),
                     ("CANONICAL delist->zero 2x", dict(delist="zero", cost_mult=2.0)),
                     ("control: BTC w/ SMA100 filter", dict(mode="btc")),
                     ("control: EW top-30 w/ SMA100", dict(mode="ew_univ"))]:
        eq, inf = bt.run(S, E, **kw)
        add(name, eq, inf)
        if name.startswith("CANONICAL (delist"):
            canon_inf = inf
    df = pd.DataFrame(rows)
    btc = df.cagr[0]; spy = df.cagr[1]
    df["vs_BTC"] = (df.cagr - btc).round(1); df["vs_SPY"] = (df.cagr - spy).round(1)
    print(df.to_string(index=False))
    df.to_csv(f"{OUT}/test_results.csv", index=False)
    pd.DataFrame(curves).to_csv(f"{OUT}/test_curves.csv")

    y = pd.DataFrame(curves).resample("YE").last()
    first = pd.DataFrame(curves).bfill().iloc[[0]]
    y = pd.concat([first, y]).pct_change().iloc[1:] * 100
    print("\nCalendar-year returns (%)"); print(y.round(1).to_string())
    held = pd.Series([s for w in canon_inf["targets"].values() for s in w.index]).value_counts()
    print("\nMost-held (weeks):", held.head(15).to_dict())
    print("Delisting events while held:", canon_inf["delist"])
    on = np.mean([len(w) > 0 for w in canon_inf["targets"].values()])
    print("Fraction of weeks invested: %.2f" % on)


if __name__ == "__main__":
    main()
