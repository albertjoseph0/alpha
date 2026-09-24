"""Leakage probe for Jev (memorisation / de-anonymisation). NOT a feature; never enters any model.
For a random sample of events (300 dev filings 2020-01..2021-06, 300 test filings 2023) we give Jev the SAME
anonymised state as s07 and ask a deliberately forbidden question about the future ("did the stock outperform the
S&P 500 over the next three months?") plus a self-report ("could you name the company?"). If Jev had memorised
outcomes and could see through the anonymisation, the forward answer would correlate with the realised 63-day
excess return (ar_63). A text-only forecaster should get roughly zero.
Also a local check: share of anonymised states that still contain the ticker or a distinctive company-name token.
Usage: s10_leak_probe.py  -> RES/leak_probe.csv, DATA/leak_probe_raw.parquet"""
import sys, gzip, json, re, time, random
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/alpha/research/round5")
from jev import ask, spent
from textprep import name_patterns, anonymise, narrative
from common import DATA, RES

E = pd.read_parquet(DATA / "events_scored.parquet")
E = E[E.ar_63.notna()]
dev = E[E.jev_ok & (E.filingDate <= "2021-06-30")].sample(300, random_state=0)
tst = E[(E.filingDate >= "2023-01-01") & (E.filingDate <= "2023-12-31")].sample(300, random_state=0)
S = pd.concat([dev.assign(period="dev_2020_21H1"), tst.assign(period="test_2023")])
want = set(S.acc)
ev = pd.read_csv(DATA / "events_8k202.csv", parse_dates=["filingDate", "accept_et"]).set_index("accessionNumber")

last, states, leak = {}, {}, {}
with gzip.open(DATA / "texts_all.jsonl.gz", "rt") as f:
    for line in f:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            break
        if d["acc"] not in ev.index:
            continue
        r = ev.loc[d["acc"]]
        if r.filingDate > pd.Timestamp("2023-12-31"):
            break
        cur = None
        if r.filingDate >= pd.Timestamp("2019-06-01"):
            pats = name_patterns(r.company, r["name"], r.ticker)
            cur = anonymise(narrative(d["text"], 12000), pats)
        prev = last.get(r.cik)
        has_prev = prev is not None and 20 <= (r.accept_et - prev[0]).days <= 200
        last[r.cik] = (r.accept_et, cur)
        if d["acc"] in want and cur and len(cur) >= 200:
            states[d["acc"]] = ("CURRENT RELEASE:\n" + cur + "\n\nPREVIOUS RELEASE:\n" +
                                (prev[1][:8000] if has_prev and prev[1] else "(not provided)"))
            toks = [t for t in re.findall(r"[A-Za-z]{5,}", str(r.company)) if t.lower() not in
                    {"corporation", "company", "holdings", "group", "international", "incorporated", "technologies",
                     "systems", "industries", "financial", "services", "energy", "global", "brands", "resources"}]
            leak[d["acc"]] = {"ticker_in_text": bool(re.search(r"\b" + re.escape(r.ticker) + r"\b", cur)) if len(r.ticker) > 2 else False,
                              "name_token_in_text": any(re.search(r"\b" + re.escape(t) + r"\b", cur, re.I) for t in toks)}
print("states", len(states), flush=True)
Q = {"fut_outperform": {"type": "noul", "instructions": "Using anything you know, did this company's stock outperform "
                        "the S&P 500 index over the three months after the CURRENT release was published?"},
     "can_name": {"type": "noul", "instructions": "Can you tell which specific, named public company issued the "
                  "CURRENT release (i.e., could you state its name)?"}}


def work(acc):
    for attempt in range(40):
        try:
            a = ask(states[acc], Q, agent="m06", retries=1, timeout=60)
            return {"acc": acc, "p_fut": a["fut_outperform"]["noul"], "p_name": a["can_name"]["noul"]}
        except Exception as e:
            if attempt < 39:
                time.sleep(0.5 + random.random() * min(1 + attempt, 8)); continue
            return {"acc": acc}


with ThreadPoolExecutor(3) as ex:
    out = list(ex.map(work, list(states)))
P = S.merge(pd.DataFrame(out), on="acc").merge(pd.DataFrame.from_dict(leak, orient="index").rename_axis("acc").reset_index(), on="acc")
P[["acc", "period", "filingDate", "ticker", "ar_63", "p_fut", "p_name", "ticker_in_text", "name_token_in_text"]].to_parquet(DATA / "leak_probe_raw.parquet")
rows = []
for per, g in P.groupby("period"):
    g = g[g.p_fut.notna()]
    rho = spearmanr(g.p_fut, g.ar_63)[0]; n = len(g)
    hit = ((g.p_fut > 0.5) == (g.ar_63 > 0)).mean()
    rows.append({"period": per, "n": n, "ic_fut_vs_ar63": rho, "t": rho * np.sqrt((n - 2) / (1 - rho ** 2)),
                 "hit_rate_sign": hit, "base_rate_up": (g.ar_63 > 0).mean(), "mean_p_fut": g.p_fut.mean(),
                 "mean_p_can_name": g.p_name.mean(), "share_p_name_gt_0.5": (g.p_name > 0.5).mean(),
                 "ticker_in_text": g.ticker_in_text.mean(), "name_token_in_text": g.name_token_in_text.mean()})
R = pd.DataFrame(rows); R.to_csv(RES / "leak_probe.csv", index=False)
print(R.round(3).to_string(index=False)); print("spent", spent("m06"))
