"""Letters -> release events (cik, dissemination date) with (a) no-text metadata, (b) keyword-rule features and
forward returns. Also validates header dissemination dates against the 2012Q1 daily-index sample.

Event = all staff letters (UPLOAD) for one CIK disseminated on the same day (normally one review 'conversation').
Point-in-time filter: the CIK is an S&P 500 member at the month-end strictly before dissemination.
Entry = close of the first trading day AFTER dissemination. Returns: buy-and-hold over H trading days, excess vs the
equal-weight average of all members (same window, members with prices) and vs SPY.

Outputs: DATA/letters.parquet (one row per letter: redacted body, forms, keyword features),
         DATA/events.parquet (one row per event: features (a), (b), returns)."""
import glob
import gzip
import json
from common import *
from textprep import redact, keyword_features

HS = [21, 63, 126, 252]


def load_letters():
    recs = []
    for f in sorted(glob.glob(str(DATA / "letters_text*.jsonl.gz"))):
        with gzip.open(f, "rt") as fh:
            for line in fh:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    L = pd.DataFrame(recs).drop_duplicates("acc")
    return L


def main():
    L = load_letters()
    Q = pd.read_csv(DATA / "qindex.csv", dtype={"date_filed": str})
    comp = dict(zip(Q.acc, Q.company))
    print("letters fetched", len(L), "errors", L.err.notna().sum(), "no hdr", L.hdr_date.isna().sum(),
          "image-pdf", L.text.str.contains(r"\[\[IMAGE_PDF", regex=True).sum())
    # --- validate header dissemination date vs daily index (2012Q1 sample) ---
    dp = DATA / "daily" / "2012Q1.partial.csv"
    if dp.exists():
        D = pd.read_csv(dp, dtype=str)
        D = D[D.form == "UPLOAD"]
        D["acc"] = D.path.str.extract(r"/([\d-]+)\.txt$")[0]
        v = L.merge(D[["acc", "dissem"]].rename(columns={"dissem": "daily"}), on="acc")
        print(f"header-date check vs daily index: {len(v)} letters, equal {(v.hdr_date == v.daily).mean():.3f}")
        if (v.hdr_date != v.daily).any():
            print(v[v.hdr_date != v.daily][["acc", "hdr_date", "daily"]].head())
    L = L[L.err.isna() & L.hdr_date.notna()].copy()
    L["dissem"] = pd.to_datetime(L.hdr_date)
    L["ldate"] = pd.to_datetime(L.acc_dt.str[:8], errors="coerce").fillna(pd.to_datetime(L.date_filed))
    L["company"] = L.acc.map(comp).fillna("")
    red = [redact(t, c) for t, c in zip(L.text, L.company)]
    L["forms"] = [r["forms"] for r in red]
    L["form_class"] = [r["form_class"] for r in red]
    L["body"] = [r["body"] for r in red]
    KF = pd.DataFrame([keyword_features(b) for b in L.body], index=L.index)
    L = pd.concat([L, KF], axis=1)
    L["image_pdf"] = L.text.str.contains(r"\[\[IMAGE_PDF", regex=True)
    L = L.drop(columns=["text"])

    # PIT membership at the month-end strictly before dissemination
    U = pd.read_csv(DATA / "universe_monthly.csv", parse_dates=["month_end"])
    L["me"] = (L.dissem - pd.offsets.MonthEnd(1)).dt.normalize()
    L = L.drop(columns=["ticker"]).merge(U.rename(columns={"month_end": "me"}), on=["me", "cik"], how="inner")
    L = L.sort_values(["cik", "dissem", "ldate"]).reset_index(drop=True)
    L["pos"] = L.groupby(["cik", "dissem"]).cumcount()
    L["n_in_event"] = L.groupby(["cik", "dissem"]).acc.transform("size")
    L.to_parquet(DATA / "letters.parquet")
    print("PIT letters", len(L))

    # ---- events ----
    kw = [c for c in KF.columns]
    g = L.groupby(["cik", "dissem"])
    E = g.agg(ticker=("ticker", "first"), me=("me", "first"), n_letters=("acc", "size"),
              first_ldate=("ldate", "min"), last_ldate=("ldate", "max"),
              form_class=("form_class", "first"), any_image=("image_pdf", "max")).reset_index()
    first = L[L.pos == 0].set_index(["cik", "dissem"])
    last = L[L.pos == L.n_in_event - 1].set_index(["cik", "dissem"])
    S = g[kw].sum()
    for c in kw:
        E[f"sum_{c}"] = S[c].values
        E[f"first_{c}"] = first.loc[list(zip(E.cik, E.dissem)), c].values
    E["last_complete"] = (last.loc[list(zip(E.cik, E.dissem)), "kw_complete"].values > 0).astype(int)
    E["last_words"] = last.loc[list(zip(E.cik, E.dissem)), "n_words"].values
    E["review_days"] = (E.dissem - E.first_ldate).dt.days
    E["release_lag"] = (E.dissem - E.last_ldate).dt.days
    E["conv_days"] = (E.last_ldate - E.first_ldate).dt.days
    # company responses (CORRESP) dated inside the conversation (first letter - 30d .. last letter)
    C = Q[Q.form == "CORRESP"].copy()
    C["d"] = pd.to_datetime(C.date_filed)
    cc = C.groupby("cik").d.apply(lambda s: np.sort(s.values))
    E["n_corresp"] = [int(((cc.get(c, np.array([], "datetime64[ns]")) >= np.datetime64(a - pd.Timedelta(days=30))) &
                           (cc.get(c, np.array([], "datetime64[ns]")) <= np.datetime64(b))).sum())
                      for c, a, b in zip(E.cik, E.first_ldate, E.last_ldate)]
    # prior events of the same CIK (history of reviews)
    E = E.sort_values(["cik", "dissem"]).reset_index(drop=True)
    E["prev_dissem"] = E.groupby("cik").dissem.shift()
    E["days_since_prev"] = (E.dissem - E.prev_dissem).dt.days
    E["n_prev_3y"] = [int(((E.cik == c) & (E.dissem < d) & (E.dissem >= d - pd.Timedelta(days=1095))).sum())
                      for c, d in zip(E.cik, E.dissem)]
    E["clean_close"] = ((E.n_letters <= 2) & (E.last_complete == 1) & (E.sum_n_comments <= 3)).astype(int)
    E["period"] = np.where(E.dissem >= TEST_START, "TEST", "DEV")

    # ---- forward returns ----
    CL = pd.read_parquet(DATA / "close.parquet")
    cal = CL["SPY"].dropna().index
    CLv = CL.values
    cols = {t: i for i, t in enumerate(CL.columns)}
    mem = U.groupby("month_end").ticker.apply(lambda s: [cols[t] for t in s.unique() if t in cols])
    for H in HS:
        E[f"r{H}"] = np.nan; E[f"ew{H}"] = np.nan; E[f"spy{H}"] = np.nan
    ent = cal.searchsorted(E.dissem.values, side="right")
    E["entry"] = [cal[i] if i < len(cal) else pd.NaT for i in ent]
    E["has_px"] = E.ticker.isin(cols)
    out = {H: [] for H in HS}
    for k, (i, t, me) in enumerate(zip(ent, E.ticker, E.me)):
        m = mem.get(me, [])
        for H in HS:
            j = i + H
            if i >= len(cal) or j >= len(cal) or t not in cols:
                out[H].append((np.nan, np.nan, np.nan)); continue
            p0, p1 = CLv[i, cols[t]], CLv[j, cols[t]]
            pm0, pm1 = CLv[i, m], CLv[j, m]
            ok = ~np.isnan(pm0) & ~np.isnan(pm1)
            ew = np.nanmean(pm1[ok] / pm0[ok] - 1) if ok.any() else np.nan
            spy = CLv[j, cols["SPY"]] / CLv[i, cols["SPY"]] - 1
            out[H].append((p1 / p0 - 1, ew, spy))
    for H in HS:
        a = np.array(out[H], dtype=float)
        E[f"r{H}"], E[f"ew{H}"], E[f"spy{H}"] = a[:, 0], a[:, 1], a[:, 2]
        E[f"x{H}"] = E[f"r{H}"] - E[f"ew{H}"]
    # pre-event momentum (12-1, info up to dissemination) as a control
    E["mom12_1"] = np.nan
    for k, (i, t) in enumerate(zip(ent, E.ticker)):
        if t in cols and i - 252 >= 0:
            p = CLv[:, cols[t]]
            d = cal.searchsorted(E.dissem.iloc[k], side="right") - 1  # last close on/before dissemination
            if d - 252 >= 0 and not np.isnan(p[d - 21]) and not np.isnan(p[d - 252]):
                E.loc[k, "mom12_1"] = p[d - 21] / p[d - 252] - 1
    E.to_parquet(DATA / "events.parquet")
    print("events", len(E), E.period.value_counts().to_dict(), "with prices", E.has_px.mean().round(3))
    print(E.groupby("period")[["n_letters", "review_days", "release_lag", "n_corresp", "clean_close"]].mean().round(2))


if __name__ == "__main__":
    main()
