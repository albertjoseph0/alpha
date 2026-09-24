"""Step B: ask Jev factual questions about the footnotes / remarks of every purchase that belongs to a
cluster event (event_members_v2), and compute the cheap dictionary baseline on the same text.

State = the purchase's own footnotes + filing remarks + the structured ownership fields, with the issuer
name, ticker, reporting-owner name and all dates stripped. Purchases whose state has no footnote/remark
text are not sent (defaults: source=not_stated, others 0; `indirect` then comes from the structured
Direct/Indirect field only). Identical states are sent once (jev.py caches by request hash).

Output: data/.../jev_purchase_v2.parquet (pid -> Jev probabilities + dictionary flags + LM counts)
usage: python 08_jev_score.py [limit]
"""
import sys, re, threading, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, "/home/user/alpha/research/round5")
import jev

D = "/home/user/alpha/data/round5/m05_insider_clusters"
AGENT = "m05"

# jev._record is a read-modify-write of the spend ledger; make it thread-safe inside this process.
_lock = threading.Lock()
_rec0 = jev._record
def _rec_locked(agent, tokens):
    with _lock:
        _rec0(agent, tokens)
jev._record = _rec_locked

Q = {
    "source": {"type": "choice",
               "instructions": "According to the text, how were the purchased shares acquired?",
               "criteria": {
                   "open_market": "bought in ordinary open-market / brokerage transactions on an exchange",
                   "offering": "bought in the issuer's public offering, IPO, rights offering or underwritten offering",
                   "private_placement": "bought directly from the issuer or another holder in a private placement, subscription or negotiated purchase agreement",
                   "plan": "bought through a dividend reinvestment plan, employee stock purchase plan, 401(k), deferred compensation or other automatic plan",
                   "not_stated": "the text does not say how the shares were acquired"}},
    "plan10b5": {"type": "noul", "instructions": "Does the text state that the purchase was made under a Rule 10b5-1 trading plan?"},
    "indirect": {"type": "noul", "instructions": "Does the text state that the purchased shares are held indirectly, e.g. by a trust, spouse or family member, fund, partnership, IRA or company, rather than directly by the reporting person?"},
    "range": {"type": "noul", "instructions": "Does the text state that the reported price is a weighted average of multiple purchases executed at a range of prices?"},
}

MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DATE_RES = [re.compile(p, re.I) for p in [
    MON + r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}", r"\d{1,2}\s+" + MON + r",?\s+\d{4}", MON + r",?\s+\d{4}",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\b\d{4}-\d{2}-\d{2}\b", r"\b(?:19|20)\d{2}\b"]]
STOP = {"inc", "corp", "corporation", "co", "company", "ltd", "llc", "lp", "the", "of", "and", "plc", "holdings",
        "group", "bancorp", "financial", "trust", "bank", "fund", "capital", "partners", "jr", "sr", "ii", "iii"}


def _tokens(name):
    return [w for w in re.split(r"[^A-Za-z0-9']+", name if isinstance(name, str) else "") if len(w) >= 3 and w.lower() not in STOP]


def anonymize(text, issuer, sym, owner):
    for d in DATE_RES:
        text = d.sub("[date]", text)
    for w in _tokens(issuer):
        text = re.sub(rf"\b{re.escape(w)}\b", "[issuer]", text, flags=re.I)
    if sym and len(sym) >= 2:
        text = re.sub(rf"\b{re.escape(sym)}\b", "[ticker]", text)
    for w in _tokens(owner):
        text = re.sub(rf"\b{re.escape(w)}\b", "[person]", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def state_of(r):
    parts = []
    if r.fn_text:
        parts.append("Footnotes: " + r.fn_text[:6000])
    if isinstance(r.remarks, str) and r.remarks.strip():
        parts.append("Remarks: " + r.remarks[:3000])
    if not parts:
        return ""
    own = "Indirect" if r.direct_indirect_ownership == "I" else "Direct"
    nat = f" ({r.nature_of_ownership})" if isinstance(r.nature_of_ownership, str) and r.nature_of_ownership.strip() else ""
    body = anonymize(" ".join(parts) + f" Ownership form: {own}{nat}.", r.issuername, r.sym, r.owner_name)
    return "Form 4 open-market purchase (transaction code P) by a company insider. " + body


# ---------------- cheap dictionary baseline ----------------
DICT = {
    "kw_offering": r"public offering|underwrit|\bIPO\b|initial public|rights offering|offering price",
    "kw_private": r"private placement|subscription agreement|securities purchase agreement|directly from the (?:issuer|company)|stock purchase agreement",
    "kw_plan": r"dividend reinvestment|\bDRIP\b|employee stock purchase|\bESPP\b|401\(k\)|deferred compensation|automatic",
    "kw_10b5": r"10b5-1|10b-5-1|10b5 1",
    "kw_indirect": r"\btrust\b|spouse|\bwife\b|husband|\bIRA\b|partnership|\bLLC\b|\bfund\b|custodian|children|family",
    "kw_range": r"weighted average|ranging from|range of prices|multiple transactions",
}


def main(limit=None):
    p = pd.read_parquet(f"{D}/purchases_v2.parquet")
    mem = pd.read_parquet(f"{D}/event_members_v2.parquet")
    pids = np.sort(mem.pid.unique())
    p = p.loc[pids].copy()
    p["fn_text"] = p.fn_text.fillna("")
    p["state"] = [state_of(r) for r in p.itertuples()]
    raw = (p.fn_text + " " + p.remarks.fillna(""))
    for k, pat in DICT.items():
        p[k] = raw.str.contains(pat, case=False, regex=True).astype(int)
    import pysentiment2 as ps
    lm = ps.LM()
    sc = [lm.get_score(lm.tokenize(t)) if t.strip() else {"Negative": 0, "Positive": 0, "Uncertainty": 0}
          for t in raw]
    p["lm_neg"] = [s["Negative"] for s in sc]; p["lm_pos"] = [s["Positive"] for s in sc]
    p["lm_unc"] = [s.get("Uncertainty", 0) for s in sc]
    uniq = [s for s in p.state.unique() if s]
    print("cluster purchases", len(p), "with text", (p.state != "").sum(), "unique states", len(uniq),
          "approx tokens", int(sum(len(s) for s in uniq) / 3.5 + 330 * len(uniq)), flush=True)
    if limit:
        uniq = uniq[:int(limit)]
    ans = {}
    t0 = time.time()

    def one(s):
        try:
            return s, jev.ask(s, Q, agent=AGENT)
        except jev.BudgetExceeded:
            raise
        except Exception as e:
            return s, {"error": repr(e)[:200]}
    with ThreadPoolExecutor(6) as ex:   # I/O-bound HTTP only, negligible CPU
        for i, (s, a) in enumerate(ex.map(one, uniq)):
            ans[s] = a
            if i % 2000 == 0:
                print(i, round(time.time() - t0), jev.spent(AGENT), flush=True)
    rows = []
    for r in p.itertuples():
        a = ans.get(r.state)
        d = dict(pid=r.Index, has_text=bool(r.state), jev_ok=a is not None and "error" not in a)
        if d["jev_ok"]:
            pr = a["source"]["probabilities"]
            for c in Q["source"]["criteria"]:
                d[f"src_{c}"] = float(pr.get(c, 0))
            d["p10b5"] = a["plan10b5"]["noul"]; d["pind"] = a["indirect"]["noul"]; d["prange"] = a["range"]["noul"]
        else:
            for c in Q["source"]["criteria"]:
                d[f"src_{c}"] = 1.0 if c == "not_stated" else 0.0
            d["p10b5"] = 0.0; d["prange"] = 0.0
            d["pind"] = 1.0 if r.direct_indirect_ownership == "I" else 0.0
        rows.append(d)
    out = pd.DataFrame(rows).set_index("pid").join(p[list(DICT) + ["lm_neg", "lm_pos", "lm_unc", "aff10b5one",
                                                                     "direct_indirect_ownership"]])
    n_err = int((out.has_text & ~out.jev_ok).sum())
    print("done; errors/unscored with text:", n_err, jev.spent(AGENT))
    out.to_parquet(f"{D}/jev_purchase_v2.parquet")
    pd.Series({s[:50]: str(a)[:300] for s, a in list(ans.items())[:30]}).to_csv(f"{D}/jev_sample_answers.csv")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
