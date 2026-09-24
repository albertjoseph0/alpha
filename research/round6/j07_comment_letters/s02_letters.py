"""Fetch the text of every SEC staff letter (UPLOAD) sent to an S&P 500 member (point-in-time, at the month-end
before dissemination), 2012-01..2026-09. One request per letter: the complete submission .txt, whose header
carries the dissemination date (': YYYYMMDD' on the SEC-HEADER line) and whose body carries the letter as a
uuencoded PDF (text extracted with PyMuPDF) or as text/HTML.

Output: DATA/letters_text.jsonl.gz (append-only, resumable), one record per accession:
  acc, cik, hdr_date, acc_dt (acceptance = letter date), docs, text (<= 60k chars), n_chars, err
Usage: s02_letters.py <from_dissem YYYYMMDD> <to_dissem YYYYMMDD> [outfile]"""
import binascii
import gzip
import json
import re
import sys

import pymupdf
from common import *

pymupdf.TOOLS.mupdf_display_errors(False)


def uudecode(block: str) -> bytes:
    out = bytearray()
    for line in block.splitlines():
        if not line or line.startswith("begin ") or line.strip() == "end":
            continue
        try:
            out += binascii.a2b_uu(line)
        except binascii.Error:
            n = (((ord(line[0]) - 32) & 63) * 4 + 5) // 3
            try:
                out += binascii.a2b_uu(line[:n])
            except binascii.Error:
                pass
    return bytes(out)


def html2text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    return s


def parse_submission(raw: str) -> dict:
    head = raw[:3000]
    m = re.search(r"<SEC-DOCUMENT>\S+ : (\d{8})", head) or re.search(r"<SEC-HEADER>\S+ : (\d{8})", head)
    hdr_date = m[1] if m else None
    m = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", head)
    acc_dt = m[1] if m else None
    texts, docs = [], []
    for d in re.findall(r"(?s)<DOCUMENT>(.*?)</DOCUMENT>", raw):
        fn = (re.search(r"<FILENAME>(\S+)", d) or [None, ""])[1]
        body = (re.search(r"(?s)<TEXT>(.*?)</TEXT>", d) or [None, ""])[1]
        docs.append(fn)
        try:
            if "<PDF>" in body[:50] or re.search(r"(?m)^begin \d+ ", body[:500]):
                pdf = uudecode(re.sub(r"</?PDF>", "", body))
                doc = pymupdf.open(stream=pdf, filetype="pdf")
                t = "\n".join(p.get_text() for p in doc)
                if len(t.strip()) < 50:
                    t = f"[[IMAGE_PDF pages={doc.page_count}]]"
            elif fn.lower().endswith((".htm", ".html")) or "<html" in body[:2000].lower():
                t = html2text(body)
            else:
                t = body
        except Exception as e:  # noqa: BLE001
            t = f"[[ERR {type(e).__name__}]]"
        texts.append(t)
    # newer submissions carry the same letter as filename1.pdf and filename2.txt: keep the text version only
    plain = [t for fn, t in zip(docs, texts) if not fn.lower().endswith(".pdf") and len(t.strip()) > 200]
    if plain and len(plain) < len(texts):
        texts = plain
    txt = "\n\n".join(texts)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n\n", txt)
    return {"hdr_date": hdr_date, "acc_dt": acc_dt, "docs": docs, "text": txt[:60000], "n_chars": len(txt)}


def targets(d0: str, d1: str) -> pd.DataFrame:
    """UPLOAD letters DATED in [d0, d1] (letter date; dissemination is read from the header) whose CIK was an
    S&P 500 member at some month-end within [letter date - 1 month, letter date + 12 months]. The exact
    point-in-time filter (member at the month-end before dissemination) is applied later, in s03."""
    L = pd.read_csv(DATA / "qindex.csv", dtype={"date_filed": str})
    L = L[(L.form == "UPLOAD") & (L.date_filed >= d0) & (L.date_filed <= d1)].copy()
    U = pd.read_csv(DATA / "universe_monthly.csv", parse_dates=["month_end"])
    L["dt"] = pd.to_datetime(L.date_filed)
    L["dissem"] = ""
    keep = []
    span = U.groupby("cik").month_end.apply(lambda s: s.values)
    for r in L.itertuples():
        m = span.get(r.cik)
        ok = m is not None and ((m >= np.datetime64(r.dt - pd.DateOffset(months=1))) &
                                (m <= np.datetime64(r.dt + pd.DateOffset(months=12)))).any()
        keep.append(ok)
    L = L[keep]
    tk = U.sort_values("month_end").groupby("cik").ticker.last()
    L["ticker"] = L.cik.map(tk)
    return L.drop_duplicates("acc").sort_values("dt")


if __name__ == "__main__":
    d0, d1 = sys.argv[1], sys.argv[2]
    outf = DATA / (sys.argv[3] if len(sys.argv) > 3 else "letters_text.jsonl.gz")
    T = targets(d0, d1)
    done = set()
    for f in DATA.glob("letters_text*.jsonl.gz"):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        done.add(json.loads(line)["acc"])
                    except json.JSONDecodeError:
                        pass
        except (EOFError, OSError):
            pass
    T = T[~T.acc.isin(done)]
    print("to fetch", len(T), "already", len(done), flush=True)
    n = 0
    for r in T.itertuples():
        url = f"https://www.sec.gov/Archives/{r.path}"
        rec = {"acc": r.acc, "cik": int(r.cik), "ticker": r.ticker, "dissem": r.dissem, "date_filed": r.date_filed}
        try:
            raw = fetch(url).decode("latin-1")
            rec.update(parse_submission(raw))
            rec["err"] = None
        except Exception as e:  # noqa: BLE001
            rec.update({"hdr_date": None, "acc_dt": None, "docs": [], "text": "", "n_chars": 0, "err": repr(e)[:200]})
        with gzip.open(outf, "at") as fh:  # one gzip member per record: robust to kills
            fh.write(json.dumps(rec) + "\n")
        n += 1
        if n % 100 == 0:
            print(n, r.dissem, r.ticker, rec["n_chars"], flush=True)
    print("done", n, flush=True)
