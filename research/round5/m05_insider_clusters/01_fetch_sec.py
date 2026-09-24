"""Download SEC insider-transaction data sets (Form 3/4/5), keep only open-market P and S
non-derivative transactions from Form 4 filings, and save compact parquet per quarter.
Raw zips are deleted after extraction."""
import os, sys, time, io, zipfile, requests
import pandas as pd

UA = "alpha-research contact@alpha-research.dev"
BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}q{}_form345.zip"
OUT = "/home/user/alpha/data/round5/m05_insider_clusters/quarters"
RAW = "/home/user/alpha/data/round5/m05_insider_clusters/raw"
os.makedirs(OUT, exist_ok=True); os.makedirs(RAW, exist_ok=True)

def rd(z, name, cols):
    with z.open(name) as f:
        return pd.read_csv(f, sep="\t", usecols=cols, dtype=str, quoting=3, on_bad_lines="skip",
                           encoding="latin-1")

def process(y, q):
    out = f"{OUT}/{y}q{q}.parquet"
    if os.path.exists(out):
        return "cached"
    zp = f"{RAW}/{y}q{q}.zip"
    if not os.path.exists(zp):
        r = requests.get(BASE.format(y, q), headers={"User-Agent": UA}, timeout=300)
        time.sleep(0.5)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        open(zp, "wb").write(r.content)
    z = zipfile.ZipFile(zp)
    sub = rd(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
                                   "ISSUERNAME", "ISSUERTRADINGSYMBOL"])
    ro = rd(z, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME",
                                      "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"])
    nt = rd(z, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "SECURITY_TITLE", "TRANS_DATE", "TRANS_CODE",
                                      "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD",
                                      "SHRS_OWND_FOLWNG_TRANS", "DIRECT_INDIRECT_OWNERSHIP"])
    # price trail: every non-derivative transaction with a price (used to recover exit prices of
    # delisted issuers: merger cash-outs (code D/U), last trades etc.)
    tr = nt[["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"]].copy()
    tr["price"] = pd.to_numeric(tr.TRANS_PRICEPERSHARE, errors="coerce")
    tr = tr[tr.price > 0].merge(sub[["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK"]], on="ACCESSION_NUMBER")
    tr["TRANS_DATE"] = pd.to_datetime(tr.TRANS_DATE, format="%d-%b-%Y", errors="coerce")
    tr["FILING_DATE"] = pd.to_datetime(tr.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    tr = tr[["ISSUERCIK", "TRANS_DATE", "FILING_DATE", "TRANS_CODE", "TRANS_ACQUIRED_DISP_CD", "price"]]
    tr.columns = [c.lower() for c in tr.columns]
    tr.to_parquet(out.replace(".parquet", "_trail.parquet"), index=False)
    nt = nt[nt.TRANS_CODE.isin(["P", "S"])]
    # collapse multiple reporting owners per filing
    ro = ro.sort_values("RPTOWNERCIK")
    rog = ro.groupby("ACCESSION_NUMBER").agg(
        owner_cik=("RPTOWNERCIK", "first"),
        owner_name=("RPTOWNERNAME", "first"),
        n_owners=("RPTOWNERCIK", "size"),
        relationship=("RPTOWNER_RELATIONSHIP", lambda s: ",".join(sorted(set(",".join(s.fillna("")).split(","))))),
        title=("RPTOWNER_TITLE", lambda s: "|".join(s.dropna().astype(str))),
    ).reset_index()
    df = nt.merge(sub, on="ACCESSION_NUMBER", how="inner").merge(rog, on="ACCESSION_NUMBER", how="left")
    df = df[df.DOCUMENT_TYPE.isin(["4", "4/A"])]
    for c in ["TRANS_SHARES", "TRANS_PRICEPERSHARE", "SHRS_OWND_FOLWNG_TRANS"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["FILING_DATE"] = pd.to_datetime(df.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    df["TRANS_DATE"] = pd.to_datetime(df.TRANS_DATE, format="%d-%b-%Y", errors="coerce")
    df.columns = [c.lower() for c in df.columns]
    df.to_parquet(out, index=False)
    z.close(); os.remove(zp)
    return f"{len(df)} rows ({(df.trans_code=='P').sum()} P)"

if __name__ == "__main__":
    for y in range(2005, 2027):
        for q in range(1, 5):
            try:
                print(y, q, process(y, q), flush=True)
            except Exception as e:
                print(y, q, "ERR", e, flush=True)
