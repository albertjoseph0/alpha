"""(a) Funding-rate squeeze, DEV only (data physically capped at 2022-12-31).

Signals use per-8h-normalised funding (fund8 = mean over the day's settlements of rate*8/interval_h).
fsig_k = rolling k-day mean of daily fund8, known at the close of day d. Weights W.loc[t] = f(signal at t-1).
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from lib import load_wide, backtest, stats, btc_returns, spy_returns, cagr_between, yearly, DEV

pd.set_option("display.width", 200)
w, _ = load_wide(cap=DEV[1])
R, ADV, F, AGE, TB = w["ret"], w["adv30"], w["fund8"], w["age"], w["tb_share"]
btc = btc_returns(w)
S0, S1 = DEV

# eligibility on day d: has funding that day, spot age >= 30 days, adv30 >= $5M
ELIG = F.notna() & (AGE >= 30) & (ADV >= 5e6)
print("eligible coins per day (median by year):")
print(ELIG.sum(1).groupby(ELIG.index.year).median())

# ---------- 1. timestamp alignment: funding vs contemporaneous / future returns ----------
print("\n== alignment: pooled Spearman-ish corr of fund8_d with ret on d-1, d, d+1, d+2 (eligible) ==")
for lag in (-1, 0, 1, 2):
    rr = R.shift(-lag)
    x = F.where(ELIG).stack()
    y = rr.where(ELIG).stack()
    j = pd.concat([x, y], axis=1, keys=["f", "r"]).dropna()
    # cross-sectional rank corr averaged over days
    cs = j.groupby(level=0).apply(lambda g: g.f.rank().corr(g.r.rank()) if len(g) > 5 else np.nan)
    print(f"  ret day d{lag:+d}: mean daily XS rank corr = {cs.mean():+.4f} (t={cs.mean()/cs.std()*np.sqrt(cs.count()):+.1f})")
bf = F[[c for c in F.columns if c.startswith("BTCUSDT#")][0]]
print("  BTC time series corr fund8_d vs ret_d:", round(bf.corr(btc), 3), " vs ret_d+1:", round(bf.corr(btc.shift(-1)), 3),
      " vs ret_d+2:", round(bf.corr(btc.shift(-2)), 3))

# ---------- 2. cross-sectional forward-return sort (information only) ----------
def fwd(h):
    # return from close d+1 to close d+1+h  (one bar lag after signal day d)
    lr = np.log1p(R.fillna(0))
    return np.expm1(lr.rolling(h).sum().shift(-(h + 1)))

print("\n== XS quintile sort on 3-day mean fund8 (Q1 = most negative); mean fwd excess vs XS mean ==")
fs3 = F.rolling(3, min_periods=2).mean().where(ELIG)
for h in (1, 3, 7, 14):
    fr = fwd(h).where(ELIG)
    rows = []
    for d in fs3.index[::1]:
        s = fs3.loc[d].dropna()
        if len(s) < 20:
            continue
        q = pd.qcut(s.rank(method="first"), 5, labels=False)
        f_ = fr.loc[d, s.index]
        ex = f_ - f_.mean()
        rows.append(ex.groupby(q).mean())
    t = pd.DataFrame(rows)
    # non-overlapping-ish t-stat: scale by sqrt(h)
    m = t.mean(); se = t.std() / np.sqrt(len(t) / h)
    print(f"  h={h:2d}d: " + "  ".join(f"Q{i+1} {m[i]*100:+.2f}% (t {m[i]/se[i]:+.1f})" for i in range(5)))

# ---------- 3. time-series squeeze strategy grid ----------
def ts_strategy(k, theta, exit_lvl=0.0, slots=5, tb_confirm=False):
    s = F.rolling(k, min_periods=1).mean()
    enter = (s < theta) & ELIG
    if tb_confirm:
        enter &= TB.rolling(3, min_periods=2).mean() > TB.rolling(30, min_periods=10).mean()
    ex = (s >= exit_lvl) | F.isna()
    state = pd.DataFrame(np.nan, index=s.index, columns=s.columns)
    state[enter] = 1.0
    state[ex & ~enter] = 0.0
    state = state.ffill().fillna(0.0)
    n = state.sum(1)
    Wt = state.div(np.maximum(n, slots), axis=0)
    return Wt.shift(1)  # decide at close d, execute at close d+1

def xs_strategy(k, n_hold, rebalance=7, side="low", tb_confirm=False):
    s = F.rolling(k, min_periods=max(1, k // 2)).mean().where(ELIG)
    if tb_confirm:
        tbx = TB.rolling(3, min_periods=2).mean() - TB.rolling(30, min_periods=10).mean()
    Wt = pd.DataFrame(0.0, index=s.index, columns=s.columns)
    last = None
    for i, d in enumerate(s.index):
        if i % rebalance == 0 or last is None:
            row = s.loc[d].dropna()
            if len(row) >= 3 * n_hold:
                if tb_confirm:
                    cand = row.nsmallest(3 * n_hold).index
                    pick = tbx.loc[d, cand].dropna().nlargest(n_hold).index
                else:
                    pick = row.nsmallest(n_hold).index if side == "low" else row.nlargest(n_hold).index
                last = pd.Series(1.0 / n_hold, index=pick)
            else:
                last = pd.Series(dtype=float)
        if last is not None and len(last):
            Wt.loc[d, last.index] = last.values
    return Wt.shift(1)

def ew_universe(rebalance=7):
    e = ELIG.astype(float)
    Wt = e.div(e.sum(1).replace(0, np.nan), axis=0).fillna(0)
    keep = np.arange(len(Wt)) % rebalance == 0
    Wt = Wt.where(pd.Series(keep, index=Wt.index), np.nan).ffill().fillna(0)
    return Wt.shift(1)

def run(label, Wt, cm=1.0, hc=0.0):
    r, turn, cost = backtest(Wt, R, ADV, cost_mult=cm, haircut=hc, start=S0, end=S1)
    r = r.loc[:S1]
    st = stats(r, label)
    st["turn_yr"] = turn.sum() / ((pd.Timestamp(S1) - pd.Timestamp(S0)).days / 365.25)
    st["cost_yr"] = cost.sum() / ((pd.Timestamp(S1) - pd.Timestamp(S0)).days / 365.25)
    st["expo"] = Wt.loc[S0:S1].sum(1).mean()
    return r, st

res, rets = [], {}
btc_c = cagr_between(btc, S0, S1)
spy_c = cagr_between(spy_returns(), S0, S1)
print(f"\nDEV {S0}..{S1}: BTC B&H CAGR {btc_c:.1%}, SPY {spy_c:.1%}")

cands = {}
for k in (1, 3):
    for th in (-0.0005, -0.001, -0.002):
        cands[f"TS k{k} th{th*100:.2f}%"] = ts_strategy(k, th)
cands["TS k3 th-0.10% +TBconfirm"] = ts_strategy(3, -0.001, tb_confirm=True)
for k in (3, 7):
    for n in (3, 5, 10):
        cands[f"XS low k{k} n{n}"] = xs_strategy(k, n)
cands["XS high k7 n5 (placebo)"] = xs_strategy(7, 5, side="high")
cands["XS low k7 n5 +TBconfirm"] = xs_strategy(7, 5, tb_confirm=True)
cands["EW eligible universe"] = ew_universe()
for lab, Wt in cands.items():
    for cm in (1.0, 2.0):
        r, st = run(lab, Wt, cm)
        st["cost_x"] = cm
        res.append(st)
        if cm == 1.0:
            rets[lab] = r
tab = pd.DataFrame(res)
tab["vs_BTC"] = tab.cagr - btc_c
tab["vs_SPY"] = tab.cagr - spy_c
print(tab[["label", "cost_x", "cagr", "vs_BTC", "vs_SPY", "maxdd", "sharpe", "expo", "turn_yr", "cost_yr"]]
      .to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print("\n== yearly returns (1x costs) ==")
yr = pd.DataFrame({k: yearly(v) for k, v in rets.items()})
yr["BTC"] = yearly(btc.loc[S0:S1])
print(yr.T.to_string(float_format=lambda x: f"{x:+.2f}"))
os.makedirs("/home/user/alpha/research/round5/m09_crypto_flow/out", exist_ok=True)
tab.to_csv("/home/user/alpha/research/round5/m09_crypto_flow/out/funding_dev_grid.csv", index=False)
pd.DataFrame(rets).to_parquet("/home/user/alpha/data/round5/m09_crypto_flow/funding_dev_rets.parquet")
