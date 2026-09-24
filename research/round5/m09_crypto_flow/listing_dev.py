"""(b) Post-listing drift on Binance spot, DEV only (data capped at 2022-12-31).

Listing event: first kline date L of a spot USDT pair's first life, L in [2019-09-01, 2022-12-31],
for a base asset that was NOT already trading on Binance in any quote currency in an earlier month
(new coin, not a new quote pair), excluding stablecoins and leveraged tokens. Relists (life 2+) excluded.
Signal known at end of day L (day 0); first execution at close of day L+1 (one full bar of lag).
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from lib import load_wide, backtest, stats, btc_returns, spy_returns, cagr_between, yearly, DEV, D

pd.set_option("display.width", 200)
QUOTES = sorted(["USDT", "BUSD", "USDC", "TUSD", "FDUSD", "BTC", "ETH", "BNB", "TRY", "EUR", "GBP", "AUD", "BRL",
                 "RUB", "BIDR", "IDRT", "NGN", "UAH", "ZAR", "PAX", "USDS", "DAI", "BKRW", "VAI", "XRP", "TRX",
                 "DOGE", "DOT", "UST", "JPY", "MXN", "PLN", "RON", "ARS", "COP", "CZK", "USDP", "AEUR", "EURI",
                 "USD1", "SOL", "USDSB", "IDR", "BVND", "GYEN", "BFUSD", "EURT", "XUSD"], key=len, reverse=True)


def listing_events(p, start, end):
    fm = pd.read_csv(f"{D}/spot_first_month.csv").dropna(subset=["first_month"])
    usdt_bases = set(p.symbol.str[:-4])

    def base(sym):
        for q in QUOTES:
            if sym.endswith(q) and len(sym) > len(q):
                b = sym[: -len(q)]
                if b in usdt_bases or q in ("USDT",):
                    return b
        for q in QUOTES:
            if sym.endswith(q) and len(sym) > len(q):
                return sym[: -len(q)]
        return None

    fm["base"] = fm.symbol.map(base)
    first_any = fm.groupby("base").first_month.min()
    firsts = p[p.sid.str.endswith("#1")].groupby("sid").agg(L=("date", "min"), symbol=("symbol", "first"))
    firsts["base"] = firsts.symbol.str[:-4]
    firsts["first_any_month"] = firsts.base.map(first_any)
    firsts["newcoin"] = firsts.first_any_month >= firsts.L.dt.strftime("%Y-%m")
    ev = firsts[(firsts.L >= start) & (firsts.L <= end)]
    return ev


if __name__ == "__main__":
    w, p = load_wide(cap=DEV[1])
    R, ADV, AGE, TB, C = w["ret"], w["adv30"], w["age"], w["tb_share"], w["close"]
    btc = btc_returns(w)
    ev = listing_events(p, "2019-09-01", DEV[1])
    print(f"USDT first-lives starting in window: {len(ev)}; new coins: {ev.newcoin.sum()}")
    ev = ev[ev.newcoin]
    print(ev.groupby(ev.L.dt.year).size())

    # ---- event study: buy close(L+1), hold H days; per-event raw and BTC-excess returns ----
    rows = []
    for sid, e in ev.iterrows():
        r = R[sid]
        L = e.L
        c0, c1 = C[sid].get(L), C[sid].get(L + pd.Timedelta(days=1))
        o0 = p.loc[(p.sid == sid) & (p.date == L), "open"]
        rec = {"sid": sid, "L": L, "d0": c0 / o0.iloc[0] - 1 if len(o0) else np.nan,
               "d1": c1 / c0 - 1 if c0 and c1 else np.nan, "tb1": TB[sid].get(L + pd.Timedelta(days=1))}
        for H in (7, 30, 90):
            win = r.loc[L + pd.Timedelta(days=2): L + pd.Timedelta(days=1 + H)]
            got = win.dropna()
            died = len(got) < H and (L + pd.Timedelta(days=1 + H)) <= pd.Timestamp(DEV[1])
            rec[f"r{H}"] = (1 + got).prod() - 1 if len(got) else np.nan
            rec[f"died{H}"] = died
            b = btc.loc[L + pd.Timedelta(days=2): L + pd.Timedelta(days=1 + H)]
            rec[f"x{H}"] = rec[f"r{H}"] - ((1 + b).prod() - 1)
        rows.append(rec)
    es = pd.DataFrame(rows)
    print("\n== per-event returns, entry close day 1 ==")
    for H in (7, 30, 90):
        x = es[f"r{H}"].dropna(); xe = es[f"x{H}"].dropna()
        print(f"H={H:2d}: n={len(x)} mean {x.mean():+.1%} median {x.median():+.1%} win {(x>0).mean():.0%} | "
              f"excess vs BTC mean {xe.mean():+.1%} median {xe.median():+.1%} (t {xe.mean()/xe.std()*np.sqrt(len(xe)):+.1f})"
              f" | died in window {es[f'died{H}'].sum()}")
    print("\nby listing year, H=30 excess vs BTC (mean, median, n):")
    print(es.groupby(es.L.dt.year).x30.agg(["mean", "median", "count"]).round(3))
    print("\nconditional on day-1 return sign (H=30 excess):")
    print(es.groupby(es.d1 > 0).x30.agg(["mean", "median", "count"]).round(3))
    print("conditional on day-1 taker-buy share > 0.5 (H=30 excess):")
    print(es.groupby(es.tb1 > 0.5).x30.agg(["mean", "median", "count"]).round(3))
    print("conditional on day-0 (open->close) return > 0 (H=30 excess):")
    print(es.groupby(es.d0 > 0).x30.agg(["mean", "median", "count"]).round(3))
    es.to_csv("/home/user/alpha/research/round5/m09_crypto_flow/out/listing_events_dev.csv", index=False)

    # ---- portfolio: hold each new listing from close(L+1) to close(L+H), slots of 1/10 ----
    newcoin = pd.Series(False, index=R.columns)
    newcoin[ev.index] = True
    S0, S1 = "2019-09-01", DEV[1]
    btc_c = cagr_between(btc, S0, S1); spy_c = cagr_between(spy_returns(), S0, S1)
    print(f"\nPortfolio DEV {S0}..{S1}: BTC {btc_c:.1%} SPY {spy_c:.1%}")
    out = []
    for H in (7, 30, 90):
        for cond in ("all", "d1>0", "tb1>0.5"):
            state = (AGE >= 0) & (AGE <= H - 1) & newcoin
            if cond != "all":
                okset = set(es.loc[(es.d1 > 0) if cond == "d1>0" else (es.tb1 > 0.5), "sid"])
                ok = pd.Series([c in okset for c in R.columns], index=R.columns)
                # conditions use day-1 data -> only decidable at close of day 1, so hold from close day 2
                state = (AGE >= 1) & (AGE <= H) & newcoin & ok
            state = state.astype(float)
            Wt = state.div(np.maximum(state.sum(1), 10), axis=0).shift(1)
            for cm in (1.0, 2.0):
                for hc in (0.0, 0.5):
                    r, turn, cost = backtest(Wt, R, ADV, cost_mult=cm, haircut=hc, start=S0, end=S1)
                    st = stats(r.loc[:S1], f"H{H} {cond}")
                    st.update(cost_x=cm, haircut=hc, expo=Wt.loc[S0:S1].sum(1).mean(),
                              vs_BTC=st["cagr"] - btc_c, vs_SPY=st["cagr"] - spy_c)
                    out.append(st)
    t = pd.DataFrame(out)
    print(t[["label", "cost_x", "haircut", "cagr", "vs_BTC", "vs_SPY", "maxdd", "sharpe", "expo"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    t.to_csv("/home/user/alpha/research/round5/m09_crypto_flow/out/listing_dev_grid.csv", index=False)
