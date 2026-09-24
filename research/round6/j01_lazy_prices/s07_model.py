"""DEV walk-forward models on identical events for three nested feature sets:
  A = price/size only; B = A + classic Lazy Prices similarity + LM tone; C = B + Jev V1 answers.
Label: sign of 63-trading-day excess return (vs SPY) minus the median over events entered in the same month.
Walk-forward: predict filing-year Y in 2016..2019 with a model trained on filings from 2014 whose label window
ended before 1 Jan Y. Also 'final' mode: train on all DEV (labels ending < 2020-01-01), predict everything later.
usage: python s07_model.py [dev|final]
Outputs: DATA/preds_dev.parquet or DATA/preds_final.parquet, metrics printed."""
import sys
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from common import *

A = ["mom12_1", "mom1", "vol60", "size_dv", "ret_d0", "is10k"]
B = A + ["cos_rf", "cos_mda", "cos_legal", "jac_rf", "jac_mda", "dlen_rf", "dlen_mda", "dlen_legal", "cos_full",
         "dlen_full", "rf_frac_new_words", "rf_frac_gone_words", "mda_frac_new_words", "mda_frac_gone_words",
         "legal_frac_new_words", "dlmneg_rf", "dlmneg_mda", "dlmpos_mda", "has_rf", "had_rf"]


def load():
    E = pd.read_parquet(DATA / "events.parquet")
    E = E[E.has_px == 1].copy()
    E["is10k"] = E.form.str.startswith("10-K").astype(int)
    E["fd"] = pd.to_datetime(E.filing_date)
    E["entry_date"] = pd.to_datetime(E.entry_date)
    E["label_end"] = E.entry_date + pd.Timedelta(days=95)
    E["ym"] = E.entry_date.dt.to_period("M")
    E["xr_dm"] = E.xret63 - E.groupby("ym").xret63.transform("median")
    E["y"] = (E.xr_dm > 0).astype(float).where(E.xret63.notna())
    jf = DATA / "jev_V1.parquet"
    J = pd.read_parquet(jf) if jf.exists() else pd.DataFrame(columns=["acc"])
    jcols = [c for c in J.columns if c.startswith("j_")]
    E = E.merge(J[["acc"] + jcols], on="acc", how="left")
    return E, jcols


def fit_predict(tr, te, cols, kind):
    Xtr, Xte = tr[cols].astype(float), te[cols].astype(float)
    if kind == "lr":
        med = Xtr.median()
        Xtr, Xte = Xtr.fillna(med), Xte.fillna(med)
        lo, hi = Xtr.quantile(0.01), Xtr.quantile(0.99)
        Xtr, Xte = Xtr.clip(lo, hi, axis=1), Xte.clip(lo, hi, axis=1)
        mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
        m = LogisticRegression(C=0.05, max_iter=2000)
        m.fit((Xtr - mu) / sd, tr.y)
        return m.predict_proba((Xte - mu) / sd)[:, 1], dict(zip(cols, m.coef_[0]))
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=200, min_samples_leaf=200,
                                       l2_regularization=1.0, random_state=0)
    m.fit(Xtr, tr.y)
    return m.predict_proba(Xte)[:, 1], {}


def monthly_ic(df, col):
    g = df.dropna(subset=[col, "xret63"]).groupby("ym")
    ics = g.apply(lambda x: x[col].corr(x.xret63, method="spearman") if len(x) > 20 else np.nan).dropna()
    return ics.mean(), ics.mean() / ics.std() * np.sqrt(len(ics)) if len(ics) > 2 else np.nan, len(ics)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    E, jcols = load()
    C = B + jcols
    sets = {"A": A, "B": B, "C": C} if jcols else {"A": A, "B": B}
    dev = E[E.fd.between(DEV_START, DEV_END)]
    if jcols:
        cov = dev[jcols[0]].notna().mean()
        print(f"Jev coverage on DEV events: {cov:.1%}")
    out = []
    if mode == "dev":
        for Y in range(2016, 2020):
            tr = dev[(dev.label_end < f"{Y}-01-01") & dev.y.notna()]
            te = dev[dev.fd.dt.year == Y].copy()
            for nm, cols in sets.items():
                for kind in ("lr", "gb"):
                    te[f"p_{nm}_{kind}"], coef = fit_predict(tr, te, cols, kind)
                    if kind == "lr" and Y == 2019:
                        print(nm, "LR coefs (2019 fold):", {k: round(v, 3) for k, v in sorted(coef.items(), key=lambda x: -abs(x[1]))[:15]})
            out.append(te)
        O = pd.concat(out)
        O.to_parquet(DATA / "preds_dev.parquet")
        lab = O[O.y.notna()]
        for c in [c for c in O.columns if c.startswith("p_")]:
            ic, t, n = monthly_ic(O, c)
            print(f"{c:10s} AUC {roc_auc_score(lab.y, lab[c]):.4f}  IC {ic:.4f} t {t:.2f} (months {n})")
        for c in B[6:] + jcols:
            ic, t, n = monthly_ic(O, c)
            print(f"  univariate {c:22s} IC {ic:+.4f} t {t:+.2f}")
    else:
        tr = dev[(dev.label_end < "2020-01-01") & dev.y.notna()]
        te = E[E.fd >= "2019-07-01"].copy()
        for nm, cols in sets.items():
            for kind in ("lr", "gb"):
                te[f"p_{nm}_{kind}"], coef = fit_predict(tr, te, cols, kind)
                if kind == "lr":
                    print(nm, {k: round(v, 3) for k, v in coef.items()})
        te.to_parquet(DATA / "preds_final.parquet")
        print("final preds:", len(te), "train n:", len(tr))


if __name__ == "__main__":
    main()
