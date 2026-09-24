"""Leakage probe: ask Jev the forbidden outcome question on 200 random DEV filings (same anonymised state) and
measure AUC against the realised 60-day abnormal return sign (about 3 months). AUC >> 0.5 would suggest
memorised outcomes."""
import json
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from common import AGENT, DATA, DEV, RES, read_texts
from state import build_state
from j02_questions import Q_LEAK
from jev import ask, spent

ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate"]).set_index("accessionNumber")
R = pd.read_parquet(DATA / "event_returns.parquet").set_index("acc")
T = {r["acc"]: r for r in read_texts()}
cand = [a for a in T if a in R.index and pd.notna(R.loc[a, "ar60"]) and DEV[0] <= str(ev.loc[a, "filingDate"].date()) <= DEV[1]]
rng = np.random.default_rng(0)
pick = rng.choice(sorted(cand), size=min(200, len(cand)), replace=False)
rows = []
for a in pick:
    ans = ask(build_state(T[a], ev.loc[a]), Q_LEAK, agent=AGENT)
    rows.append({"acc": a, "p": ans["outperf"]["noul"], "ar60": R.loc[a, "ar60"], "ar20": R.loc[a, "ar20"]})
L = pd.DataFrame(rows)
L.to_csv(DATA / "leak_probe.csv", index=False)
res = {"n": len(L), "auc_ar60": roc_auc_score(L.ar60 > 0, L.p), "auc_ar20": roc_auc_score(L.ar20 > 0, L.p),
       "p_mean": L.p.mean(), "p_std": L.p.std(), "p_quantiles": L.p.quantile([0.1, 0.5, 0.9]).round(3).tolist(),
       "spend": spent(AGENT)}
# bootstrap CI for AUC
bs = []
for _ in range(1000):
    s = L.sample(len(L), replace=True, random_state=_)
    if (s.ar60 > 0).nunique() == 2:
        bs.append(roc_auc_score(s.ar60 > 0, s.p))
res["auc_ar60_ci90"] = [float(np.quantile(bs, 0.05)), float(np.quantile(bs, 0.95))]
print(json.dumps(res, indent=1, default=float))
(RES / "leak_probe.json").write_text(json.dumps(res, indent=1, default=float))
