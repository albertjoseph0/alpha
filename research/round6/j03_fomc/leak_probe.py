"""Leakage probe (brief step 3). On ~200 DEV documents (all DEV statements + a random sample of DEV minutes,
anonymised exactly like the feature states) ask Jev FORBIDDEN questions about what happened afterwards, and
measure accuracy against realised outcomes. Also ask Jev to date the text (if it can date it, it may know outcomes).
Legitimate-information control: the AUC of the no-LLM dictionary score for the same outcomes.
Output: data/round6/j03_fomc/leak_probe.parquet, printed summary.
"""
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
from jev import spent  # noqa: E402
from jev_features import ask  # noqa: E402  (same client, with 503 retry)

D = ROOT / "data" / "round6" / "j03_fomc"
Q = {
    "spx_up_12m": {"type": "noul", "instructions": "Did the U.S. stock market (S&P 500) end higher 12 months after this Federal "
                   "Reserve document was released than on the day it was released?"},
    "y10_up_12m": {"type": "noul", "instructions": "Was the 10-year U.S. Treasury yield higher 12 months after this Federal Reserve "
                   "document was released than on the day it was released?"},
    "spx_beat_bonds_3m": {"type": "noul", "instructions": "Over the 3 months after this Federal Reserve document was released, did "
                          "U.S. stocks outperform long-term U.S. Treasury bonds?"},
    "era": {"type": "choice", "instructions": "In which period was this Federal Reserve document most likely written?",
            "criteria": {"1994_1998": None, "1999_2003": None, "2004_2008": None, "2009_2012": None, "2013_or_later": None}},
}


def auc(score, y):
    s, y = np.asarray(score, float), np.asarray(y, int)
    ok = np.isfinite(s)
    s, y = s[ok], y[ok]
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    gt = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    return gt


def boot_auc_ci(score, y, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    s, y = np.asarray(score, float), np.asarray(y, int)
    v = [auc(s[i], y[i]) for i in (rng.integers(0, len(s), len(s)) for _ in range(n))]
    return np.nanpercentile(v, [2.5, 97.5])


def main():
    d = pd.read_parquet(D / "docs.parquet")
    px = pd.read_parquet(D / "prices.parquet")
    dev = d[d.period == "DEV"]
    rng = np.random.default_rng(3)
    mins = dev[dev.kind == "M"]
    sample = pd.concat([dev[dev.kind == "S"], mins.loc[rng.choice(mins.index, size=max(0, 200 - (dev.kind == "S").sum()), replace=False)]])
    spx = (1 + px.SPY_cc.fillna(0)).cumprod()
    tlt = (1 + px.TLT_cc.fillna(0)).cumprod()
    y10 = px.DGS10
    idx = px.index
    rows = []
    for _, r in sample.iterrows():
        a = ask(r.text, Q, agent="j03")
        i0 = idx.get_loc(r.event_date)
        i12, i3 = min(i0 + 252, len(idx) - 1), min(i0 + 63, len(idx) - 1)
        rows.append(dict(kind=r.kind, event_date=r.event_date, dict_net=r.dict_net,
                         p_spx=a["spx_up_12m"]["noul"], p_y10=a["y10_up_12m"]["noul"], p_sb=a["spx_beat_bonds_3m"]["noul"],
                         era=a["era"]["choice"],
                         spx_up=int(spx.iloc[i12] > spx.iloc[i0]), y10_up=int(y10.iloc[i12] > y10.iloc[i0]),
                         sb=int(spx.iloc[i3] / spx.iloc[i0] > tlt.iloc[i3] / tlt.iloc[i0])))
    p = pd.DataFrame(rows)
    yr = p.event_date.dt.year
    p["era_true"] = np.select([yr <= 1998, yr <= 2003, yr <= 2008], ["1994_1998", "1999_2003", "2004_2008"], "2009_2012")
    p.to_parquet(D / "leak_probe.parquet")
    res = []
    for q, t in (("p_spx", "spx_up"), ("p_y10", "y10_up"), ("p_sb", "sb")):
        for kind in ("all", "S", "M"):
            s = p if kind == "all" else p[p.kind == kind]
            a = auc(s[q], s[t])
            lo, hi = boot_auc_ci(s[q].values, s[t].values)
            ad = auc(s.dict_net, s[t])
            res.append(dict(question=q, docs=kind, n=len(s), base_rate=s[t].mean(), jev_auc=a, ci_lo=lo, ci_hi=hi,
                            dict_auc_same_target=ad, dict_auc_flipped=1 - ad))
    res = pd.DataFrame(res)
    print(res.round(3).to_string(index=False))
    res.to_csv(D / "leak_probe_summary.csv", index=False)
    acc = (p.era == p.era_true).mean()
    print("era accuracy", round(acc, 3), "(chance ~0.25-0.30); confusion:")
    print(pd.crosstab(p.era_true, p.era))
    print("spent", spent("j03"))


if __name__ == "__main__":
    main()
