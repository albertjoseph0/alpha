"""Event-level feature sets (a) no text, (b) + keyword rules, (c) + Jev, and the pre-specified rule flags."""
from common import *
from questions import TOPICS

FORM_CLASSES = ["periodic", "deal", "registration", "proxy", "other"]
KWS = ["kw_rev", "kw_nongaap", "kw_segment", "kw_impair", "kw_gc", "kw_restate", "kw_repeat", "kw_complete",
       "kw_future", "kw_tellus", "kw_loss", "kw_tax"]


def jev_event_features(L: pd.DataFrame, J: pd.DataFrame) -> pd.DataFrame:
    """Aggregate letter-level Jev answers to events (cik, dissem)."""
    X = L[["acc", "cik", "dissem", "pos", "n_in_event"]].merge(J, on="acc", how="left")
    X["subst"] = X.j_complete < 0.5
    g = X.groupby(["cik", "dissem"])
    out = pd.DataFrame({
        "jv_sev_max": g.j_severity.max(),
        "jv_sev_mean": g.j_severity.mean(),
        "jv_restate_max": g.j_restate.max(),
        "jv_repeat_max": g.j_repeat.max(),
        "jv_n_subst": g.subst.sum(),
        "jv_scored": g.j_severity.count(),
    })
    first = X[X.pos == 0].set_index(["cik", "dissem"])
    last = X[X.pos == X.n_in_event - 1].set_index(["cik", "dissem"])
    out["jv_sev_first"] = first.j_severity
    out["jv_complete_last"] = last.j_complete
    S = X[X.subst]
    gs = S.groupby(["cik", "dissem"])
    for k in TOPICS:
        out[f"jv_top_{k}"] = gs[f"j_topic_{k}"].max()
    tcols = [f"jv_top_{k}" for k in TOPICS]
    out[tcols] = out[tcols].fillna(0.0)
    out["jv_topic"] = out[tcols].idxmax(axis=1).str.replace("jv_top_", "")
    out.loc[out[tcols].max(axis=1) == 0, "jv_topic"] = "none"
    return out.reset_index()


def build_sets(E: pd.DataFrame):
    E = E.copy()
    A = pd.DataFrame(index=E.index)
    A["n_letters"] = E.n_letters
    A["n_corresp"] = E.n_corresp
    A["log_review_days"] = np.log1p(E.review_days.clip(lower=0))
    A["log_release_lag"] = np.log1p(E.release_lag.clip(lower=0))
    A["log_conv_days"] = np.log1p(E.conv_days.clip(lower=0))
    A["n_prev_3y"] = E.n_prev_3y
    A["log_days_since_prev"] = np.log1p(E.days_since_prev.fillna(3650).clip(upper=3650))
    for f in FORM_CLASSES[1:]:
        A[f"form_{f}"] = (E.form_class == f).astype(int)
    B = A.copy()
    for k in KWS:
        B[f"sum_{k}"] = np.log1p(E[f"sum_{k}"])
    B["first_n_comments"] = np.log1p(E.first_n_comments)
    B["sum_n_comments"] = np.log1p(E.sum_n_comments)
    B["log_words"] = np.log1p(E.sum_n_words)
    B["last_complete_kw"] = E.last_complete
    C = B.copy()
    jcols = ["jv_sev_max", "jv_sev_mean", "jv_sev_first", "jv_restate_max", "jv_repeat_max", "jv_complete_last",
             "jv_n_subst"] + [f"jv_top_{k}" for k in TOPICS]
    for c in jcols:
        C[c] = E[c]
    return {"A_notext": A.fillna(0.0), "B_keywords": B.fillna(0.0), "C_jev": C.fillna(0.0)}


def rule_flags(E: pd.DataFrame) -> pd.DataFrame:
    """Pre-specified rules (fixed before looking at DEV returns; logged in README)."""
    F = pd.DataFrame(index=E.index)
    F["R_A_long_review"] = (E.n_letters >= 4).astype(int)                       # no text: >= 4 staff letters
    F["R_K_restate_kw"] = (E.sum_kw_restate >= 1).astype(int)                   # keywords: restate/amend/MW
    F["R_J_high_sev"] = ((E.jv_sev_max >= 3) | (E.jv_restate_max >= 0.5)).astype(int)  # Jev: significant+ or restate ask
    F["CC_A_single"] = (E.n_letters == 1).astype(int)                           # no text: single-letter release
    F["CC_K_clean"] = E.clean_close.astype(int)                                  # keywords: <=2 letters, complete, <=3 comments
    F["CC_J_clean"] = ((E.n_letters <= 2) & (E.jv_complete_last >= 0.5) & (E.jv_sev_max <= 1.5)).astype(int)
    return F
