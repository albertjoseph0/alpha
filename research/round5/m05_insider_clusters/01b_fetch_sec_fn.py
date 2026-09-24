"""Round 5b: (re)download SEC insider-transaction data sets and keep, per quarter,
  * the compact P/S file + price trail (same format as 01_fetch_sec.py) if still missing, and
  * NEW `{yq}_pfn.parquet`: every Form 4 / 4/A non-derivative code-P row with its transaction SK,
    ownership fields, the footnote ids attached to the row, the footnote TEXT, the filing REMARKS,
    the AFF10B5ONE checkbox (exists only from 2023) and the collapsed reporting-owner fields.
Zips are deleted after extraction. Safe to re-run (skips quarters whose outputs exist)."""
import os, time, zipfile, requests, importlib.util
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("f01", f"{HERE}/01_fetch_sec.py")
f01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f01)
UA, BASE, OUT, RAW = f01.UA, f01.BASE, f01.OUT, f01.RAW


def rd_all(z, name):
    with z.open(name) as f:
        return pd.read_csv(f, sep="\t", dtype=str, quoting=3, on_bad_lines="skip", encoding="latin-1")


def owners(ro):
    ro = ro.sort_values("RPTOWNERCIK")
    return ro.groupby("ACCESSION_NUMBER").agg(
        owner_cik=("RPTOWNERCIK", "first"), owner_name=("RPTOWNERNAME", "first"),
        n_owners=("RPTOWNERCIK", "size"),
        relationship=("RPTOWNER_RELATIONSHIP", lambda s: ",".join(sorted(set(",".join(s.fillna("")).split(","))))),
        title=("RPTOWNER_TITLE", lambda s: "|".join(s.dropna().astype(str))),
    ).reset_index()


def pfn(z, out):
    sub = rd_all(z, "SUBMISSION.tsv")
    keep = ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERNAME",
            "ISSUERTRADINGSYMBOL", "REMARKS"] + (["AFF10B5ONE"] if "AFF10B5ONE" in sub.columns else [])
    sub = sub[keep]
    sub = sub[sub.DOCUMENT_TYPE.isin(["4", "4/A"])]
    nt = rd_all(z, "NONDERIV_TRANS.tsv")
    nt = nt[nt.TRANS_CODE == "P"]
    nt = nt[nt.ACCESSION_NUMBER.isin(sub.ACCESSION_NUMBER)]
    fncols = [c for c in nt.columns if c.endswith("_FN")]
    ids = nt[fncols].fillna("").agg(",".join, axis=1)
    nt["fn_ids"] = ids.map(lambda s: ",".join(sorted({x.strip() for x in s.split(",") if x.strip()},
                                                        key=lambda v: (len(v), v))))
    fn = rd_all(z, "FOOTNOTES.tsv")
    fn = fn[fn.ACCESSION_NUMBER.isin(set(nt.ACCESSION_NUMBER))]
    fmap = {(a, i): (t or "") for a, i, t in zip(fn.ACCESSION_NUMBER, fn.FOOTNOTE_ID, fn.FOOTNOTE_TXT.fillna(""))}
    nt["fn_text"] = [" ".join(f"[{i}] {fmap.get((a, i), '')}" for i in s.split(",") if i)
                     for a, s in zip(nt.ACCESSION_NUMBER, nt.fn_ids)]
    ro = rd_all(z, "REPORTINGOWNER.tsv")
    ro = ro[ro.ACCESSION_NUMBER.isin(set(nt.ACCESSION_NUMBER))]
    cols = ["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "SECURITY_TITLE", "TRANS_DATE", "TRANS_CODE",
            "TRANS_TIMELINESS", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD",
            "SHRS_OWND_FOLWNG_TRANS", "DIRECT_INDIRECT_OWNERSHIP", "NATURE_OF_OWNERSHIP", "fn_ids", "fn_text"]
    df = nt[[c for c in cols if c in nt.columns]].merge(sub, on="ACCESSION_NUMBER").merge(
        owners(ro), on="ACCESSION_NUMBER", how="left")
    for c in ["TRANS_SHARES", "TRANS_PRICEPERSHARE", "SHRS_OWND_FOLWNG_TRANS"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["FILING_DATE", "TRANS_DATE"]:
        df[c] = pd.to_datetime(df[c], format="%d-%b-%Y", errors="coerce")
    df.columns = [c.lower() for c in df.columns]
    df.to_parquet(out, index=False)
    return len(df)


def process(y, q):
    main = f"{OUT}/{y}q{q}.parquet"; outp = f"{OUT}/{y}q{q}_pfn.parquet"
    if os.path.exists(main) and os.path.exists(outp):
        return "cached"
    zp = f"{RAW}/{y}q{q}.zip"
    if not os.path.exists(zp):
        r = requests.get(BASE.format(y, q), headers={"User-Agent": UA}, timeout=300)
        time.sleep(0.5)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        open(zp + ".part", "wb").write(r.content); os.replace(zp + ".part", zp)
    z = zipfile.ZipFile(zp)
    msg = ""
    if not os.path.exists(outp):
        msg += f"pfn {pfn(z, outp)} rows; "
    z.close()
    if not os.path.exists(main):
        msg += "main " + f01.process(y, q)   # deletes the zip
    if os.path.exists(zp):
        os.remove(zp)
    return msg


if __name__ == "__main__":
    for y in range(2006, 2027):
        for q in range(1, 5):
            if (y, q) > (2026, 1):
                break
            try:
                print(y, q, process(y, q), flush=True)
            except Exception as e:
                print(y, q, "ERR", repr(e), flush=True)
