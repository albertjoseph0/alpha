"""Parse each 424B4 text: IPO confirmation, SPAC/unit flags, ticker, exchange, offer price, shares,
lead underwriter, and the prospectus sections for Jev. Also computes keyword-rule features (set b).
Outputs: meta.csv (one row per filing), sections.jsonl.gz (sections, not anonymised)."""
import re, gzip, json
import pandas as pd
from common import DATA

TXT = DATA / "txt"
c = pd.read_csv(DATA / "candidates.csv", parse_dates=["date"])
c = c[~c.spac_name]

TOP = [("goldman", r"goldman"), ("morgan_stanley", r"morgan stanley"), ("jpmorgan", r"j\.\s?p\.\s?morgan"),
       ("bofa", r"merrill lynch|bofa|banc of america|bank of america"), ("citi", r"citigroup|citi\b"),
       ("credit_suisse", r"credit suisse"), ("barclays", r"barclays"), ("deutsche", r"deutsche bank")]


def flat(t):
    return re.sub(r"\s+", " ", t)


def best_section(f, head, score, window=6000, skip_toc=True):
    best, bpos = -1, None
    for m in re.finditer(head, f, re.I):
        nxt = f[m.end(): m.end() + window]
        if skip_toc and re.match(r"\s*\|?\s*(?:page\s*)?\d{1,3}\s*\|", nxt):
            continue
        s = len(re.findall(score, nxt, re.I))
        if s >= best:  # ties -> later occurrence
            best, bpos = s, m.start()
    return (f[bpos: bpos + window], best) if bpos is not None else ("", 0)


rows, n = [], 0
with gzip.open(DATA / "sections.tmp.gz", "wt") as fo:
    for r in c.itertuples():
        p = TXT / f"{r.acc}.txt.gz"
        if not p.exists():
            continue
        f = flat(gzip.decompress(p.read_bytes()).decode(errors="replace"))
        cov = f[:6000]
        d = dict(acc=r.acc, cik=r.cik, company=r.company, date=r.date.date(), reg_form=r.reg_form, nchar=len(f))
        d["ipo_text"] = bool(re.search(r"initial public offering|no (?:established )?public (?:trading )?market|"
                                       r"not been a public market|no public market", cov, re.I))
        d["blank_check"] = bool(re.search(r"blank check|special purpose acquisition|initial business combination", f[:30000], re.I))
        d["units"] = bool(re.search(r"\bunits?\b[^.]{0,120}(?:consist|each unit)|each unit consist", cov, re.I))
        d["warrants_cover"] = bool(re.search(r"warrant", cov[:1500], re.I))
        d["best_efforts"] = bool(re.search(r"best efforts", cov, re.I))
        d["ads"] = bool(re.search(r"American Depositary", cov[:1500], re.I))
        m = re.search(r"under the (?:trading )?symbols?\s*[“\"”'‘’]*\s*([A-Z]{1,5}(?:[.\-][A-Z]{1,2})?)(?![A-Za-z])", cov)
        d["ticker"] = m.group(1).rstrip(".") if m else None
        if d["ticker"] and (d["ticker"].endswith(".U") or (len(d["ticker"]) == 5 and d["ticker"].endswith("U"))):
            d["units"] = True
        m = re.search(r"(Nasdaq|NASDAQ|New York Stock Exchange|NYSE MKT|NYSE American|NYSE Amex|NYSE)", cov)
        d["exchange"] = ("nasdaq" if m and "asdaq" in m.group(1).lower() else
                         "amex" if m and re.search("MKT|American|Amex", m.group(1)) else "nyse" if m else None)
        cnp = re.sub(r"\s+", " ", cov.replace("|", " "))
        m = (re.search(r"(?:initial public offering price|price to (?:the )?public|public offering price|initial price of)"
                       r"[^$]{0,250}?\$\s?([\d,]*\d\.\d{2})", cnp, re.I)
             or re.search(r"\$\s?([\d,]*\d\.\d{2})\s*(?:per share|per ADS)", cnp, re.I))
        d["offer_price"] = float(m.group(1).replace(",", "")) if m else None
        m = re.search(r"([\d,]{5,})\s+(?:Shares|shares|American Depositary|ADSs)", cov[:1500])
        d["shares_offered"] = float(m.group(1).replace(",", "")) if m else None
        MON = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        md = re.search(r"deliver(?:y of)?[^.]{0,250}?" + MON + r"\s+\d{1,2},\s+\d{4}\.?", cov, re.I)
        st = md.end() if md else 0
        me = re.search(r"prospectus dated|the date of this prospectus|" + MON + r"\s+\d{1,2},\s+\d{4}", cov[st:], re.I)
        uw = cov[st: st + me.start()] if (me and md) else (cov[max(0, st + me.start() - 300): st + me.start()] if me else "")
        uw = re.sub(r"Neither the .*?criminal offense\.", " ", uw)
        d["uw_snip"] = uw[:200]
        lead = None
        for name, pat in TOP:
            mm = re.search(pat, uw[:120], re.I)
            if mm and (lead is None or mm.start() < lead[1]):
                lead = (name, mm.start())
        d["kw_top_lead"] = lead is not None
        d["kw_top_any"] = any(re.search(pat, uw, re.I) for _, pat in TOP)
        d["selling_only"] = bool(re.search(r"we are not (?:offering|selling) any|not receive any (?:of the )?proceeds from (?:this|the) offering", cov, re.I))
        d["has_selling_holders"] = bool(re.search(r"selling (?:stock|share)holders?", cov, re.I))
        secs = {}
        mt = re.compile(r"table of contents\s*\|", re.I).search(cov, 400)
        secs["cover"] = cov[: min(3500, mt.start() if mt else 3500)]
        def direct(pat, n, flags=re.I):
            mm = re.search(pat, f, flags)
            return f[mm.start(): mm.start() + n] if mm else ""
        secs["summary"] = direct(r"summary\s+(?:This|The following) summary (?:highlights|provides|contains)", 9000) or \
            direct(r"PROSPECTUS SUMMARY\s+(?!\|)", 9000, 0)
        if not secs["summary"]:
            secs["summary"], _ = best_section(f[:len(f) // 2], r"prospectus summary|summary", r"summary highlights|overview|our company|our business", 1200)
            if secs["summary"]:
                i0 = f.find(secs["summary"]); secs["summary"] = f[i0: i0 + 9000]
        secs["uop"], d["uop_score"] = best_section(f, r"use of proceeds", r"proceeds", 4500)
        secs["risk"] = direct(r"risk factors\s+(?:An )?(?:investing|investment|an investment) in (?:our|the|shares|these)", 9000) or \
            best_section(f, r"risk factors", r"adversely", 9000)[0]
        secs["pss"], d["pss_score"] = best_section(f, r"principal (?:and selling )?(?:stock|share)holders|security ownership of certain beneficial",
                                                   r"beneficial", 6000)
        secs["sfd"] = direct(r"SUMMARY (?:CONSOLIDATED |HISTORICAL |COMBINED |SELECTED |PRO FORMA |AND |FINANCIAL )+(?:FINANCIAL )?(?:AND OPERATING |AND OTHER )?(?:DATA|INFORMATION)\s+(?!\|\s*\d)", 4000, 0) or \
            best_section(f, r"summary (?:consolidated |historical |combined |selected |financial )+(?:financial )?(?:and operating )?(?:data|information)",
                         r"net (?:income|loss|\(loss\))", 4000)[0]
        full_lo = f.lower()
        s_all = " ".join(secs.values()).lower()
        d["kw_netloss"] = bool(re.search(r"history of (?:net )?losses|have incurred (?:significant )?(?:net )?losses|not (?:yet )?(?:been|achieved) profitab|may never (?:achieve|become) profitab", secs["risk"] + secs["summary"], re.I))
        d["kw_accum_deficit"] = "accumulated deficit" in s_all
        d["kw_repay"] = bool(re.search(r"repay|redeem|redemption of|pay down|prepay", secs["uop"], re.I))
        d["kw_pay_holders"] = bool(re.search(r"distribution to|dividend to (?:our )?(?:existing|pre-offering)|purchase (?:shares|units|interests) from|to redeem .{0,50}(?:units|interests)|tax receivable|pay (?:the )?(?:accrued|cumulative) dividends", secs["uop"], re.I))
        d["kw_sponsor"] = bool(re.search(r"venture|private equity|sponsor|capital partners|equity partners|ventures\b|funds? affiliated", secs["pss"] + secs["summary"], re.I))
        d["kw_dual"] = bool(re.search(r"class b common stock|ten votes|10 votes|twenty votes|dual[- ]class|multiple[- ]class", s_all, re.I))
        d["kw_controlled"] = "controlled company" in full_lo[:400000]
        d["kw_mw"] = "material weakness" in full_lo
        d["kw_customer_conc"] = bool(re.search(r"(?:significant|substantial|large) portion of our (?:revenue|net sales|sales)|limited number of (?:customers|clients)|(?:largest|top (?:\w+ )?)customers? (?:accounted|represented)", s_all, re.I))
        d["kw_egc"] = "emerging growth company" in cov.lower()
        d["kw_going_concern"] = "going concern" in full_lo
        d["kw_nrisk"] = len(re.findall(r"adversely affect", full_lo))
        rows.append(d)
        fo.write(json.dumps({"acc": r.acc, **secs}) + "\n")
        n += 1
(DATA / "sections.tmp.gz").replace(DATA / "sections.jsonl.gz")
m = pd.DataFrame(rows)
m.to_csv(DATA / "meta.tmp.csv", index=False)
(DATA / "meta.tmp.csv").replace(DATA / "meta.csv")
print(n, m[["ipo_text", "blank_check", "units", "warrants_cover", "best_efforts", "ads", "kw_top_lead", "selling_only",
            "kw_netloss", "kw_repay", "kw_sponsor", "kw_dual", "kw_controlled", "kw_mw", "kw_customer_conc"]].mean().round(2))
print("ticker", m.ticker.notna().mean(), "price", m.offer_price.notna().mean(), "shares", m.shares_offered.notna().mean())
