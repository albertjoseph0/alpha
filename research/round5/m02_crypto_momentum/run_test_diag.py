"""Post-TEST artifact hunt (no rule changes; the frozen rule is not re-tuned).
(a) Per-coin P&L attribution of the frozen rule by year, TEST.
(b) Cross-sectional signal check, every Sunday, DEV and TEST, BTC filter ignored:
    within the top-30 liquid universe, next-week return (Mon close t+1 -> Mon close t+8) of the top-5
    momentum coins minus the universe equal-weight average, plus the rank IC.
(c) Capacity of the frozen rule in TEST (sqrt impact)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/alpha/research/round5/m02_crypto_momentum")
import backtest as bt

OUT = "/home/user/alpha/research/round5/m02_crypto_momentum"
S, E = "2022-01-01", "2026-08-31"


def attribution(inf, start, end):
    close, _, _ = bt.load()
    ret = close.loc[start:end].pct_change(fill_method=None)
    tg = inf["targets"]; keys = sorted(tg)
    W = pd.DataFrame(0.0, index=ret.index, columns=sorted({c for v in tg.values() for c in v.index}))
    for i, te in enumerate(keys):
        nxt = keys[i + 1] if i + 1 < len(keys) else ret.index[-1] + pd.Timedelta(days=1)
        span = (W.index > te) & (W.index <= nxt)
        W.loc[span, :] = 0.0
        for c, x in tg[te].items():
            W.loc[span, c] = x
    return (W * ret[W.columns].fillna(0)).groupby(W.index.year).sum()


def xs_check(start, end, p=bt.DEFAULT):
    close, qv, _ = bt.load()
    live = close.notna(); age = live.cumsum()
    liq = qv.rolling(30, min_periods=15).mean()
    mom = close / close.shift(28) - 1
    idx = close.index; pos = {d: i for i, d in enumerate(idx)}
    rows = []
    for t in pd.date_range(start, end, freq="W-SUN"):
        if t not in pos or pos[t] + 8 >= len(idx): continue
        a, b = idx[pos[t] + 1], idx[pos[t] + 8]
        elig = live.loc[t] & (age.loc[t] >= 60) & liq.loc[t].notna() & mom.loc[t].notna()
        U = liq.loc[t][elig].sort_values(ascending=False).head(30).index
        if len(U) < 10: continue
        fwd = close.loc[b, U] / close.loc[a, U] - 1  # delisted within the week -> NaN, dropped
        m = mom.loc[t, U]
        ok = fwd.notna()
        top = m[ok].sort_values(ascending=False).head(5).index
        rows.append(dict(t=t, spread=fwd[top].mean() - fwd[ok].mean(),
                         ic=m[ok].rank().corr(fwd[ok].rank())))
    return pd.DataFrame(rows).set_index("t")


def main():
    eq, inf = bt.run(S, E)
    c = attribution(inf, S, E)
    for y in c.index:
        s = c.loc[y].sort_values()
        print(f"{y} sum {s.sum():+.2f}; best:", {k: round(v, 2) for k, v in s.tail(4)[::-1].items()},
              "worst:", {k: round(v, 2) for k, v in s.head(5).items()})
    c.T.to_csv(f"{OUT}/test_attribution.csv")

    print("\nCross-sectional check (top-5 by 28d mom minus top-30 EW, next week; filter ignored)")
    out = []
    for name, (a, b) in {"DEV 2018-21": ("2018-01-01", "2021-12-31"), "DEV 2018-20": ("2018-01-01", "2020-12-31"),
                         "TEST 2022-26": (S, E)}.items():
        x = xs_check(a, b)
        n = len(x)
        print(f"{name}: weeks={n} mean spread {100*x.spread.mean():+.2f}%/wk "
              f"t={x.spread.mean()/x.spread.std()*np.sqrt(n):.2f}; mean rank IC {x.ic.mean():+.3f} "
              f"t={x.ic.mean()/x.ic.std()*np.sqrt(n):.2f}")
        x["period"] = name; out.append(x)
    pd.concat(out).to_csv(f"{OUT}/xs_momentum_check.csv")

    print("\nCapacity TEST (frozen rule + sqrt impact)")
    for aum in [0, 1e5, 1e6, 1e7]:
        print(f"  ${aum:,.0f}: CAGR {100*bt.stats(bt.run(S, E, aum=aum)[0])['cagr']:.1f}")


if __name__ == "__main__":
    main()
