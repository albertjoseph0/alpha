"""Which Jev questions mattered: (a) univariate monthly rank IC (NW t) of each Jev feature and each text
feature vs the 63-day excess return; (b) logistic coefficients of the price+jev model fit on all dev events;
(c) permutation importance (drop in pooled OOF-style IC when a question's columns are shuffled within month).
Usage: s09_jev_importance.py dev|test   (test: univariate IC on 2023+ filings only)"""
import sys
import numpy as np, pandas as pd
import s08_model as M   # MODE taken from argv by s08_model
from common import RES

E = M.E
if M.MODE == "test":
    E = E[E.filingDate >= M.TEST_START]
feats = M.JEV + [c for c in M.DICT + M.FB + M.PRICE if c not in M.JEV]
rows = []
for c in dict.fromkeys(feats):
    st = M.ic_stats(E.assign(_f=E[c].astype(float)), "_f")
    rows.append({"feature": c, "group": "jev" if c in M.JEV else ("price" if c in M.PRICE else "dict/finbert"),
                 "mean": E[c].mean(), **st})
U = pd.DataFrame(rows).sort_values("t_nw")
U.to_csv(RES / f"feature_ic_{M.MODE}.csv", index=False)
pd.set_option("display.width", 200)
print(U[["feature", "group", "mean", "ic_mean", "t_nw", "n_months"]].round(4).to_string(index=False))

if M.MODE == "dev":
    cols = M.PRICE + M.JEV
    tr = E[E.y.notna()]
    m = M.model("logit").fit(M.ranked(tr, cols), tr.y.values)
    co = pd.Series(m.coef_[0], index=cols).sort_values()
    co.to_csv(RES / "coef_price_jev_dev.csv")
    print("\nlogit coefficients (price+jev, all dev):"); print(co.round(3).to_string())
    # permutation importance on the purged LOYO out-of-fold score
    base = M.scores("logit", cols)[0]
    E["_s"] = base; b = M.ic_stats(E, "_s")["ic_mean"]
    qs = sorted({c.split("__")[0] for c in M.JEV})
    rng = np.random.default_rng(0); out = []
    for q in qs:
        qc = [c for c in M.JEV if c.split("__")[0] == q]
        E2 = E.copy()
        for c in qc:
            E2[c] = E2.groupby("ym")[c].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values)
        M.E = E2
        E2["_s"] = M.scores("logit", cols)[0]
        out.append({"question": q, "ic_drop": b - M.ic_stats(E2, "_s")["ic_mean"]})
        M.E = E
    P = pd.DataFrame(out).sort_values("ic_drop", ascending=False)
    P.to_csv(RES / "jev_perm_importance_dev.csv", index=False)
    print("\nbase OOF IC", round(b, 4)); print(P.round(4).to_string(index=False))
