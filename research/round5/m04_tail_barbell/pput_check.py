"""Historical cross-check of the pricer against the real CBOE PPUT index (1990-2026).

PPUT (Cboe S&P 500 5% Put Protection Index) holds the S&P 500 (dividends reinvested) and buys, every
month on the roll date (the monthly SPX expiration Friday), one 1-month SPX put with strike about 5%
below the index, held to expiration. Real traded prices are used by Cboe. We replicate it with our
model-priced puts (linz and SSVI surfaces calibrated only to that day's VIX-family indices and SKEW)
and compare yearly returns. What differs between replication and PPUT is almost entirely the
put premium paid, so this tests the model's historical 5%-OTM, 1-month put level
(not the 20-30% OTM wing the barbell uses; the only check of that wing is the 2026 chain).

Replication: roll on the last trading day <= 3rd Friday of each month; the expiring put pays
max(K - S_close, 0) (close proxies the AM SOQ); new strike = largest multiple of 5 <= 0.95 S;
units n = V / (S + P*(1+h)) so equity + puts = V.  h = 0 (mid) and 2.5% (buy at ask).
Outputs: pput_check_yearly.csv, pput_check.txt
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from backtest import load, Pricer, third_friday  # noqa: E402

OUT = Path(__file__).parent


def replicate(df, pr, h):
    idx = df.index
    S = df.SPX.values
    r_tr = df.r_tr.values
    # roll days: last trading day <= third Friday
    rolls = set()
    for y in range(idx[0].year, idx[-1].year + 1):
        for m in range(1, 13):
            tf = third_friday(y, m)
            prior = idx[idx <= tf]
            if len(prior) and (tf - prior[-1]).days < 5 and prior[-1] >= idx[0]:
                rolls.add(prior[-1])
    V = np.empty(len(idx))
    eqv, n, K, exp = 1.0, 0.0, 0.0, None
    for i, dt in enumerate(idx):
        if i > 0:
            eqv *= 1 + r_tr[i]
        mark = n * pr.put(i, K, max((exp - dt).days, 0) / 365) if n > 0 else 0.0
        if dt in rolls or i == 0:
            if n > 0 and dt >= exp - pd.Timedelta(days=4):
                mark = n * max(K - S[i], 0.0)
            tot = eqv + mark
            K = 5.0 * math.floor(0.95 * S[i] / 5.0)
            exp = third_friday(dt.year + (dt.month // 12), dt.month % 12 + 1)
            tau = (exp - dt).days / 365
            P = pr.put(i, K, tau) * (1 + h)
            n = tot / (S[i] + P)
            eqv = n * S[i]
            mark = n * pr.put(i, K, tau)
            tot = eqv + mark
        V[i] = eqv + mark
    return pd.Series(V, index=idx)


def main():
    df = load("_s21")
    raw = load("")
    df["r_tr"] = pd.read_pickle(Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell/panel.pkl")["r_tr"].reindex(df.index).fillna(0.0)
    pput = pd.read_pickle(Path(__file__).resolve().parents[3] / "data/round5/m04_tail_barbell/panel.pkl")["PPUT"].reindex(df.index).ffill()
    res = {"PPUT": pput / pput.iloc[0]}
    raw["r_tr"] = df["r_tr"]
    for tag, d in [("raw", raw), ("s21", df)]:
        for mod in ["linz", "ssvi"]:
            pr = Pricer(d, mod)
            for h in [0.0, 0.025]:
                res[f"{mod}_{tag}_h{h}"] = replicate(d, pr, h)
    tr = (1 + df.r_tr).cumprod()
    res["SP500TR"] = tr / tr.iloc[0]
    V = pd.DataFrame(res)
    y = V.resample("YE").last()
    y = y.pct_change().fillna(y.iloc[0] - 1)
    y.index = y.index.year
    y.to_csv(OUT / "pput_check_yearly.csv", float_format="%.4f")
    lines = []
    for per, a, b in [("DEV 1990-2007", "1990", "2007"), ("TEST 2008-2026", "2008", "2026"), ("ALL", "1990", "2026")]:
        sub = V.loc[a:b]
        yrs = (sub.index[-1] - sub.index[0]).days / 365.25
        c = (sub.iloc[-1] / sub.iloc[0]) ** (1 / yrs) - 1
        lines.append(f"{per}: CAGR " + ", ".join(f"{k} {v:.4f}" for k, v in c.items()))
        # annual premium drag vs SP500TR implied: PPUT CAGR - model CAGR
    dy = y.sub(y["PPUT"], axis=0).drop(columns=["PPUT"])
    lines.append("yearly (replication - PPUT): mean / sd / corr of yearly returns")
    for col in dy.columns:
        if col == "SP500TR":
            continue
        lines.append(f"  {col}: mean {dy[col].mean():+.4f} sd {dy[col].std():.4f} corr {y[col].corr(y['PPUT']):.3f}")
    for per, a, b in [("1990-1999", 1990, 1999), ("2000-2007", 2000, 2007), ("2008-2026", 2008, 2026)]:
        sub = dy.loc[a:b]
        lines.append(f"  {per} mean yearly diff: " + ", ".join(f"{k} {v:+.4f}" for k, v in sub.mean().items()))
    txt = "\n".join(lines)
    print(txt)
    print(y.round(3).to_string())
    (OUT / "pput_check.txt").write_text(txt + "\n\n" + y.round(4).to_string() + "\n")


if __name__ == "__main__":
    main()
