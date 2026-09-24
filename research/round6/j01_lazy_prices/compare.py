"""Year-on-year comparison of filing sections: pairing, classic Lazy Prices similarity measures, LM tone,
and a paragraph-level diff used as Jev's state (anonymised)."""
import math
import re
from collections import Counter

from extract import paragraphs

_W = re.compile(r"[a-z]{2,}")
SECS = ("rf", "mda", "legal")


def words(t):
    return _W.findall(t.lower())


def cosine_counts(a: Counter, b: Counter):
    if not a or not b:
        return math.nan
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb)


def jaccard(a: set, b: set):
    if not a or not b:
        return math.nan
    return len(a & b) / len(a | b)


def sim_features(cur: dict, pri: dict):
    """Classic Lazy Prices measures per section (cosine TF, Jaccard on word sets, log length change)
    plus full-document cosine on the hashed bag of words."""
    out = {}
    for s in SECS:
        a, b = cur.get(s, ""), pri.get(s, "")
        wa, wb = words(a), words(b)
        out[f"has_{s}"] = int(bool(wa))
        out[f"had_{s}"] = int(bool(wb))
        out[f"cos_{s}"] = cosine_counts(Counter(wa), Counter(wb))
        out[f"jac_{s}"] = jaccard(set(wa), set(wb))
        out[f"dlen_{s}"] = math.log((len(wa) + 50) / (len(wb) + 50))
    ba = {int(k): v for k, v in cur["bow"].items()}
    bb = {int(k): v for k, v in pri["bow"].items()}
    out["cos_full"] = cosine_counts(Counter(ba), Counter(bb))
    out["dlen_full"] = math.log((cur["n_chars"] + 1000) / (pri["n_chars"] + 1000))
    return out


def para_diff(cur_text: str, pri_text: str, thr: float = 0.5):
    """Paragraphs of the current version with no close match (word-set Jaccard >= thr) in the prior version,
    and vice versa. Numbers are ignored (only words), so updated figures do not count as changes.
    Candidates come from an inverted index on rarer words; paragraphs with no rare word are compared to all."""
    pc, pp = paragraphs(cur_text or ""), paragraphs(pri_text or "")
    wc = [words(p) for p in pc]
    wp = [words(p) for p in pp]
    sc = [set(w) for w in wc]
    sp = [set(w) for w in wp]

    def index(sets):
        df = Counter(w for st in sets for w in st)
        lim = max(3, int(0.05 * len(sets)))
        inv = {}
        for j, st in enumerate(sets):
            for w in st:
                if df[w] <= lim:
                    inv.setdefault(w, []).append(j)
        return inv, {frozenset(st) for st in sets}

    def best(s, others, idx):
        inv_, exact = idx
        if frozenset(s) in exact:
            return 1.0
        cnt = Counter()
        for w in s:
            js = inv_.get(w)
            if js:
                cnt.update(js)
        cand = [j for j, _ in cnt.most_common(5)] if cnt else range(len(others))
        b = 0.0
        for j in cand:
            o = others[j]
            inter = len(s & o)
            b = max(b, inter / (len(s) + len(o) - inter))
        return b

    ip, ic = index(sp), index(sc)
    newi = [i for i, s in enumerate(sc) if s and best(s, sp, ip) < thr]
    gonei = [i for i, s in enumerate(sp) if s and best(s, sc, ic) < thr]
    ncur = sum(len(w) for w in wc)
    npri = sum(len(w) for w in wp)
    return [pc[i] for i in newi], [pp[i] for i in gonei], {
        "n_par_cur": len(pc), "n_par_pri": len(pp), "n_new": len(newi), "n_gone": len(gonei),
        "frac_new_words": sum(len(wc[i]) for i in newi) / max(ncur, 1),
        "frac_gone_words": sum(len(wp[i]) for i in gonei) / max(npri, 1)}


_MONTHS = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?"


def anonymise(t: str, name_pats, ticker: str):
    for p in name_pats:
        t = p.sub("the Company", t)
    if ticker:
        t = re.sub(r"\b" + re.escape(ticker) + r"\b", "[TICKER]", t)
    t = re.sub(r"(?i)\b" + _MONTHS + r"\s+\d{1,2},?\s+(19|20)\d\d\b", "[DATE]", t)
    t = re.sub(r"(?i)\b" + _MONTHS + r"\s+(19|20)\d\d\b", "[DATE]", t)
    t = re.sub(r"\b\d{1,2}/\d{1,2}/(19|20)?\d\d\b", "[DATE]", t)
    t = re.sub(r"\b(fiscal\s+)?(19|20)\d\d\b", lambda m: (m.group(1) or "") + "[YEAR]", t, flags=re.I)
    return t


_SUFFIX = re.compile(r"(?i)\b(inc|incorporated|corp|corporation|co|company|ltd|plc|llc|lp|l\.p|n\.v|s\.a|holdings?|group|the|de|/de/|/new/)\b\.?")


def name_patterns(name: str):
    """Regexes for the company name and its distinctive leading word(s)."""
    if not isinstance(name, str):
        return []
    base = re.sub(r"/.*?/", " ", name)
    core = _SUFFIX.sub(" ", base.replace(",", " ")).split()
    pats = []
    if core:
        full = r"\s+".join(re.escape(w) for w in core)
        pats.append(re.compile(r"(?i)\b" + full + r"(\s+(inc|corp|corporation|company|co|ltd|plc|holdings|group)\b\.?)?"))
        if len(core[0]) >= 4 and core[0].lower() not in {"american", "first", "general", "united", "national",
                                                          "international", "southern", "western", "eastern"}:
            pats.append(re.compile(r"(?i)\b" + re.escape(core[0]) + r"(’s|'s)?\b"))
    return pats


def jev_state(new_old: dict, form: str, name: str, ticker: str, max_chars: dict):
    """new_old: {sec: (new_paragraphs, gone_paragraphs, prior_available)} -> anonymised dict state."""
    npats = name_patterns(name)
    labels = {"rf": "risk_factors", "mda": "management_discussion", "legal": "legal_proceedings"}
    st = {"document": "annual report (10-K)" if form.startswith("10-K") else
          "quarterly report (10-Q), compared with the same quarter one year earlier",
          "note": "Only paragraphs that differ between the two versions are shown. 'added_in_current' = text in "
                  "the current version with no close counterpart in the prior version; 'removed_from_prior' = text "
                  "in the prior version that no longer appears. Unchanged text is omitted."}
    for s, (new, gone, prior_ok, cur_ok) in new_old.items():
        cap = max_chars[s]

        def take(lst, c):
            out, n = [], 0
            for p in lst:
                p = anonymise(p, npats, ticker)
                if n + len(p) > c:
                    if c - n > 300:
                        out.append(p[: c - n] + " ...")
                    out.append(f"[... {len(lst) - len(out)} more paragraphs truncated]")
                    break
                out.append(p)
                n += len(p)
            return out
        st[labels[s]] = {"section_present_in_current": cur_ok, "section_present_in_prior": prior_ok,
                         "added_in_current": take(new, int(cap * 0.65)),
                         "removed_from_prior": take(gone, int(cap * 0.35))}
    return st
