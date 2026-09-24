"""Leakage probe. usage: s06_leak.py select | analyze
select: 200 DEV events (dissemination 2012-2019, 12-month excess return known), one letter each (the first letter
        of the event), fixed seed -> DATA/leak_sample.csv. Then run `s05_jev.py leak 2012-01-01 2019-12-31`.
analyze: AUC of Jev's forbidden answer ('did the stock outperform the market over the next 12 months?') against the
        realized outcome (vs the EW S&P 500 and vs SPY). AUC > 0.55 would suggest Jev knows outcomes."""
import sys
from common import *


def auc(score, y):
    s, y = np.asarray(score, float), np.asarray(y, int)
    ok = ~np.isnan(s)
    s, y = s[ok], y[ok]
    r = pd.Series(s).rank().values
    n1, n0 = y.sum(), len(y) - y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot_ci(score, y, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    s, y = np.asarray(score, float), np.asarray(y, int)
    a = [auc(s[i], y[i]) for i in (rng.integers(0, len(s), len(s)) for _ in range(n))]
    return np.percentile(a, [2.5, 97.5])


if sys.argv[1] == "select":
    E = pd.read_parquet(DATA / "events.parquet")
    E = E[(E.period == "DEV") & E.x252.notna()]
    S = E.sample(200, random_state=2024)
    L = pd.read_parquet(DATA / "letters.parquet", columns=["acc", "cik", "dissem", "pos"])
    S = S.merge(L[L.pos == 0], on=["cik", "dissem"])
    S[["acc", "cik", "dissem", "ticker", "x252", "r252", "spy252"]].to_csv(DATA / "leak_sample.csv", index=False)
    print("sample", len(S), "share outperforming EW", (S.x252 > 0).mean().round(3))
else:
    S = pd.read_csv(DATA / "leak_sample.csv")
    J = pd.read_parquet(DATA / "jev_leak.parquet")
    S = S.merge(J, on="acc")
    p = S.j_outperform_12m
    y1 = (S.x252 > 0).astype(int)
    y2 = (S.r252 > S.spy252).astype(int)
    out = []
    for name, y in [("vs EW S&P 500", y1), ("vs SPY", y2)]:
        a = auc(p, y)
        lo, hi = boot_ci(p.values, y.values)
        out.append((name, len(S), round(y.mean(), 3), round(a, 3), f"[{lo:.3f}, {hi:.3f}]"))
    R = pd.DataFrame(out, columns=["outcome", "n", "base rate", "AUC", "95% CI"]).set_index("outcome")
    print(R)
    print("answer distribution:", p.describe().round(3).to_dict())
    R.to_csv(OUT / "leak_probe.csv")
