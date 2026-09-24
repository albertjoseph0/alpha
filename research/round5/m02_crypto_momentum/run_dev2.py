"""DEV diagnostics (2018-2021 only): where does the canonical excess come from?
(a) weekly excess vs BTC buy&hold and vs the BTC+SMA100 control, t-stats, top-week concentration;
(b) approximate per-coin P&L attribution by year (target weights x daily returns, no drift);
(c) canonical started 2019-01-01 (Binance had only 6-19 USDT pairs in 2018)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5/m02_crypto_momentum")
import backtest as bt

S, E = "2018-01-01", "2021-12-31"
OUT = "/home/user/alpha/research/round5/m02_crypto_momentum"


def main():
    eq, inf = bt.run(S, E)
    eqf, _ = bt.run(S, E, mode="btc")
    btc = bt.bench_btc(S, E)
    pd.DataFrame({"canonical": eq, "btc_filter": eqf, "btc": btc}).to_csv(f"{OUT}/dev_curves.csv")
    w = pd.DataFrame({k: v.resample("W-MON").last() for k, v in
                      dict(c=eq, f=eqf, b=btc).items()}).pct_change().dropna()
    for name, ex in [("vs BTC buy&hold", w.c - w.b), ("vs BTC+SMA100 control", w.c - w.f)]:
        lx = np.log1p(w.c) - np.log1p(w.b if "hold" in name else w.f)
        t = ex.mean() / ex.std() * np.sqrt(len(ex))
        top = lx.sort_values(ascending=False)
        print(f"{name}: weeks={len(ex)} mean weekly excess {100*ex.mean():.2f}% t={t:.2f}; "
              f"total log excess {lx.sum():.2f}; minus best 5 weeks {lx.sum()-top.head(5).sum():.2f}; "
              f"minus best 10 {lx.sum()-top.head(10).sum():.2f}")
        for y in [2018, 2019, 2020, 2021]:
            e = ex[ex.index.year == y]
            print(f"   {y}: mean {100*e.mean():+.2f}%/wk t={e.mean()/e.std()*np.sqrt(len(e)):.2f}")

    # (b) attribution
    close, _, _ = bt.load()
    ret = close.loc[S:E].pct_change(fill_method=None)
    tg = inf["targets"]
    W = pd.DataFrame(0.0, index=ret.index, columns=sorted({c for v in tg.values() for c in v.index}))
    keys = sorted(tg)
    for i, te in enumerate(keys):
        nxt = keys[i + 1] if i + 1 < len(keys) else ret.index[-1] + pd.Timedelta(days=1)
        span = (W.index > te) & (W.index <= nxt)
        W.loc[span, :] = 0.0
        for c, x in tg[te].items():
            W.loc[span, c] = x
    contrib = (W * ret[W.columns].fillna(0)).groupby(W.index.year).sum()
    for y in contrib.index:
        s = contrib.loc[y].sort_values()
        print(f"{y} sum of simple contributions {s.sum():+.2f}; top 5:",
              {k: round(v, 2) for k, v in s.tail(5)[::-1].items()},
              "bottom 3:", {k: round(v, 2) for k, v in s.head(3).items()})
    contrib.T.to_csv(f"{OUT}/dev_attribution.csv")

    # (c) 2019-start
    print("\nStart 2019-01-01 (universe >= 19 pairs):")
    for name, kw in [("canonical", {}), ("BTC+filter", dict(mode="btc"))]:
        for end in ["2020-12-31", "2021-12-31"]:
            s = bt.stats(bt.run("2019-01-01", end, **kw)[0])
            print(f"  {name} 2019->{end[:4]}: CAGR {100*s['cagr']:.1f}")
    for end in ["2020-12-31", "2021-12-31"]:
        print(f"  BTC b&h 2019->{end[:4]}: CAGR {100*bt.stats(bt.bench_btc('2019-01-01', end))['cagr']:.1f}")


if __name__ == "__main__":
    main()
