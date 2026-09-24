"""s01: download the SEC Form 13F structured data sets one ZIP at a time, reduce each to small parquet files,
then delete the ZIP (disk budget).

sec.py's `get` decodes the body to text (it would corrupt a binary ZIP) and caches in the shared cache (several GB
for 13F), so this script reuses sec.py's shared cross-process rate limiter (`_wait_turn`) and the exact SEC User-Agent,
and streams each ZIP into data/orch/o03_13f_best_ideas/raw/ instead.

Per ZIP it writes (to data/orch/o03_13f_best_ideas/proc/<tag>_*.parquet):
  filings  : one row per 13F-HR / 13F-HR/A submission (accession, cik, manager name, filing date, period, report type,
             amendment flag, n equity positions, total equity value in $)
  agg      : per (period, cusip, early) the sum of $ value, shares and number of filers over ORIGINAL 13F-HR filings,
             where early = filed on/before the formation cutoff of that period (see cutoff_date). Used as the
             point-in-time "market portfolio" proxy and for 13F-implied prices (value/shares).
  pos      : full position lists (cusip-level) of original 13F-HR filings with 5..150 equity positions and >= $50M
             (a superset of the qualifying-manager rule, so the rule can be applied later).
Equity position = SSHPRNAMTTYPE == 'SH' and PUTCALL empty. VALUE is in $ thousands for filings before 2023-01-03 and in
$ for filings from 2023-01-03 (SEC change); both are converted to $.

Usage: .venv/bin/python research/orch/o03_13f_best_ideas/s01_fetch13f.py [first_tag] [last_tag]
"""
import io
import os
import re
import sys
import time
import zipfile
import pathlib
import urllib.request

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "round5"))
import sec  # noqa: E402

D = ROOT / "data" / "orch" / "o03_13f_best_ideas"
RAW = D / "raw"
PROC = D / "proc"
PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"


def cutoff_date(period: pd.Timestamp) -> pd.Timestamp:
    """Formation cutoff: filings with FILING_DATE <= period end + 46 calendar days are 'known' at formation.
    (Deadline is 45 days after quarter end; the portfolio is formed from filings dated up to one day after it
    and traded at the close of the next trading day after the cutoff; see s03.)"""
    return period + pd.Timedelta(days=46)


def list_zips() -> list[str]:
    html = sec.get(PAGE, cache=False)
    links = re.findall(r'href="([^"]*form13f\.zip)"', html, flags=re.I)
    return sorted(set("https://www.sec.gov" + l if l.startswith("/") else l for l in links))


def tag_of(url: str) -> str:
    return url.rsplit("/", 1)[1].replace("_form13f.zip", "")


def download(url: str, path: pathlib.Path) -> None:
    if path.exists() and zipfile.is_zipfile(path):
        return
    tmp = path.with_suffix(".part")
    delay = 5.0
    for attempt in range(6):
        sec._wait_turn()
        req = urllib.request.Request(url, headers={"User-Agent": sec.UA, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            tmp.rename(path)
            return
        except Exception as e:  # noqa: BLE001
            print("  retry", attempt, repr(e), flush=True)
            time.sleep(delay); delay *= 2
    raise RuntimeError(f"download failed {url}")


def norm_cusip(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.upper().str.replace(r"[^0-9A-Z]", "", regex=True)
    return s.where(s.str.len() != 8, "0" + s)  # leading zero dropped by some filers


def find(z: zipfile.ZipFile, stem: str) -> str:
    for n in z.namelist():
        if n.upper().endswith(stem.upper() + ".TSV"):
            return n
    raise KeyError(stem)


def read_tsv(z, stem, usecols=None, **kw):
    with z.open(find(z, stem)) as f:
        return pd.read_csv(f, sep="\t", dtype=str, usecols=usecols, quoting=3, on_bad_lines="skip",
                           encoding="latin-1", **kw)


def process(path: pathlib.Path, tag: str) -> None:
    z = zipfile.ZipFile(path)
    sub = read_tsv(z, "SUBMISSION")
    cov = read_tsv(z, "COVERPAGE")
    summ = read_tsv(z, "SUMMARYPAGE")
    sub.columns = [c.upper() for c in sub.columns]
    cov.columns = [c.upper() for c in cov.columns]
    summ.columns = [c.upper() for c in summ.columns]
    f = sub[["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"]].copy()
    ccols = [c for c in ["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "REPORTTYPE", "ISAMENDMENT", "AMENDMENTTYPE",
                         "REPORTCALENDARORQUARTER"] if c in cov.columns]
    f = f.merge(cov[ccols], on="ACCESSION_NUMBER", how="left")
    scols = [c for c in ["ACCESSION_NUMBER", "OTHERINCLUDEDMANAGERSCOUNT", "TABLEENTRYTOTAL", "TABLEVALUETOTAL",
                         "ISCONFIDENTIALOMITTED"] if c in summ.columns]
    f = f.merge(summ[scols], on="ACCESSION_NUMBER", how="left")
    f = f[f.SUBMISSIONTYPE.isin(["13F-HR", "13F-HR/A"])].copy()
    f["filing_date"] = pd.to_datetime(f.FILING_DATE, format="mixed", dayfirst=False)
    f["period"] = pd.to_datetime(f.PERIODOFREPORT, format="mixed", dayfirst=False)
    f["cutoff"] = f.period.map(cutoff_date)
    f["early"] = f.filing_date <= f.cutoff
    f["mult"] = np.where(f.filing_date >= pd.Timestamp("2023-01-03"), 1.0, 1000.0)
    f["amend"] = (f.SUBMISSIONTYPE == "13F-HR/A")
    meta = f.set_index("ACCESSION_NUMBER")

    usecols = ["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE",
               "PUTCALL"]
    parts = []
    with z.open(find(z, "INFOTABLE")) as fh:
        hdr = fh.readline().decode("latin-1").rstrip("\r\n").split("\t")
        cols = [c.upper() for c in hdr]
    with z.open(find(z, "INFOTABLE")) as fh:
        it = pd.read_csv(fh, sep="\t", dtype=str, header=0, names=cols, usecols=usecols, quoting=3,
                         on_bad_lines="skip", encoding="latin-1", chunksize=400_000)
        for ch in it:
            ch = ch[ch.ACCESSION_NUMBER.isin(meta.index)]
            ch = ch[(ch.SSHPRNAMTTYPE.str.strip().str.upper() == "SH") & (ch.PUTCALL.isna() | (ch.PUTCALL.str.strip() == ""))]
            ch = ch.drop(columns=["SSHPRNAMTTYPE", "PUTCALL"])
            ch["CUSIP"] = norm_cusip(ch.CUSIP)
            ch["VALUE"] = pd.to_numeric(ch.VALUE, errors="coerce")
            ch["SSHPRNAMT"] = pd.to_numeric(ch.SSHPRNAMT, errors="coerce")
            ch = ch.dropna(subset=["VALUE", "SSHPRNAMT"])
            ch["VALUE"] = ch.VALUE * meta.loc[ch.ACCESSION_NUMBER, "mult"].to_numpy()
            # collapse to cusip level within each filing (rows split by discretion / other manager)
            g = ch.groupby(["ACCESSION_NUMBER", "CUSIP"], sort=False).agg(
                value=("VALUE", "sum"), shares=("SSHPRNAMT", "sum"),
                issuer=("NAMEOFISSUER", "first"), title=("TITLEOFCLASS", "first")).reset_index()
            parts.append(g)
    pos = pd.concat(parts, ignore_index=True)
    # a filing can straddle chunks: collapse again
    pos = pos.groupby(["ACCESSION_NUMBER", "CUSIP"], sort=False).agg(
        value=("value", "sum"), shares=("shares", "sum"), issuer=("issuer", "first"),
        title=("title", "first")).reset_index()
    del parts
    stats = pos.groupby("ACCESSION_NUMBER").agg(n_pos=("CUSIP", "size"), tot_value=("value", "sum"))
    f = f.merge(stats, left_on="ACCESSION_NUMBER", right_index=True, how="left")
    f["n_pos"] = f.n_pos.fillna(0).astype(int)
    f["tot_value"] = f.tot_value.fillna(0.0)
    keep = ["ACCESSION_NUMBER", "CIK", "FILINGMANAGER_NAME", "SUBMISSIONTYPE", "REPORTTYPE", "ISAMENDMENT",
            "AMENDMENTTYPE", "OTHERINCLUDEDMANAGERSCOUNT", "TABLEENTRYTOTAL", "TABLEVALUETOTAL",
            "filing_date", "period", "cutoff", "early", "amend", "n_pos", "tot_value"]
    f = f[[c for c in keep if c in f.columns]]
    PROC.mkdir(parents=True, exist_ok=True)
    f.to_parquet(PROC / f"{tag}_filings.parquet", index=False)

    orig = f[~f.amend].set_index("ACCESSION_NUMBER")
    p2 = pos[pos.ACCESSION_NUMBER.isin(orig.index)].copy()
    p2["period"] = orig.loc[p2.ACCESSION_NUMBER, "period"].to_numpy()
    p2["early"] = orig.loc[p2.ACCESSION_NUMBER, "early"].to_numpy()
    agg = p2.groupby(["period", "CUSIP", "early"]).agg(
        value=("value", "sum"), shares=("shares", "sum"), n_filers=("ACCESSION_NUMBER", "nunique"),
        issuer=("issuer", "first"), title=("title", "first")).reset_index()
    # 13F-implied price: median over filers of value/shares (robust to a few mis-scaled filers)
    p2["px"] = p2.value / p2.shares.replace(0, np.nan)
    pxm = p2.groupby(["period", "CUSIP"]).px.median().rename("px_med").reset_index()
    agg = agg.merge(pxm, on=["period", "CUSIP"], how="left")
    agg.to_parquet(PROC / f"{tag}_agg.parquet", index=False)

    cand = orig[(orig.n_pos >= 5) & (orig.n_pos <= 150) & (orig.tot_value >= 50e6)].index
    pos[pos.ACCESSION_NUMBER.isin(cand)].to_parquet(PROC / f"{tag}_pos.parquet", index=False)
    print(f"  {tag}: filings {len(f)} orig {len(orig)} positions {len(pos)} agg {len(agg)} cand {len(cand)}",
          flush=True)


def main():
    urls = list_zips()
    tags = [tag_of(u) for u in urls]
    print(len(urls), "zips:", tags[0], "...", tags[-1], flush=True)
    lo = sys.argv[1] if len(sys.argv) > 1 else None
    hi = sys.argv[2] if len(sys.argv) > 2 else None

    def key(t):  # sortable key for both naming schemes
        m = re.match(r"(\d{4})q(\d)", t)
        if m:
            return f"{m.group(1)}-{int(m.group(2)) * 3:02d}"
        d = pd.Timestamp(t.split("-")[1])
        return f"{d.year}-{d.month:02d}"

    order = sorted(zip(urls, tags), key=lambda x: key(x[1]))
    RAW.mkdir(parents=True, exist_ok=True)
    for url, tag in order:
        if lo and key(tag) < key(lo):
            continue
        if hi and key(tag) > key(hi):
            continue
        if (PROC / f"{tag}_pos.parquet").exists():
            continue
        t0 = time.time()
        path = RAW / f"{tag}.zip"
        download(url, path)
        t1 = time.time()
        process(path, tag)
        path.unlink()
        print(f"  {tag}: download {t1 - t0:.0f}s process {time.time() - t1:.0f}s", flush=True)


if __name__ == "__main__":
    main()
