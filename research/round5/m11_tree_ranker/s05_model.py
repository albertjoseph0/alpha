"""Walk-forward tree ranker + controls.

usage: s05_model.py dev              -> run all DEV configs (logged), pick best by DEV mean rank IC
       s05_model.py test <config>    -> run the frozen config on TEST once (after PREREG.md)

Walk-forward: retrain every December formation (expanding window); a model trained at formation F
uses only rows whose label window has closed (t1 <= F). DEV holding months 2014-01..2019-12
(2012-2013 = warm-up / first training window). TEST holding months 2020-01..2026-08.
"""
import sys
import time
from common import *  # sets OMP_NUM_THREADS=1 before sklearn loads OpenMP
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from common import *

FEATS = ["mom12_1", "mom6_1", "rev1", "resmom", "hi52", "vol1", "vol12", "maxret1", "beta", "ivol",
         "secmom", "size_dv", "dv_trend", "amihud", "logprice", "short_ratio", "short_chg", "is500"]
K = 25
COST500, COST400 = 0.0005, 0.0012  # one-way, per side
CONFIGS = {
    "hgb_l7_i100": dict(kind="hgb", max_leaf_nodes=7, max_iter=100),
    "hgb_l7_i300": dict(kind="hgb", max_leaf_nodes=7, max_iter=300),
    "hgb_l31_i100": dict(kind="hgb", max_leaf_nodes=31, max_iter=100),
    "hgb_l31_i300": dict(kind="hgb", max_leaf_nodes=31, max_iter=300),
    "rf_baseline": dict(kind="rf"),
    "ridge_linear": dict(kind="ridge"),
}
DEV = ("2013-12-01", "2019-11-30")   # formation dates -> holding 2014-01..2019-12
TEST = ("2019-12-01", "2026-07-31")  # formation dates -> holding 2020-01..2026-08


def load():
    P = pd.read_parquet(DATA / "panel.parquet")
    months = pd.read_csv(DATA / "months.csv", parse_dates=["form", "t0", "t1"])
    X = P.groupby("form")[FEATS].rank(pct=True) - 0.5
    X["is500"] = P["is500"] - 0.5
    P[[f"x_{c}" for c in FEATS]] = X.values
    P["y"] = P.groupby("form")["ret"].rank(pct=True) - 0.5
    P = P.merge(months[["form", "t0", "t1", "n_mem", "n_nodata", "n_nodata_exit"]], on="form", how="left")
    return P, months


def make_model(cfg):
    if cfg["kind"] == "hgb":
        return HistGradientBoostingRegressor(learning_rate=0.05, max_leaf_nodes=cfg["max_leaf_nodes"],
                                             max_iter=cfg["max_iter"], min_samples_leaf=500,
                                             l2_regularization=1.0, early_stopping=False, random_state=0)
    if cfg["kind"] == "rf":
        return RandomForestRegressor(n_estimators=200, min_samples_leaf=500, max_features=0.33,
                                     max_samples=0.5, n_jobs=1, random_state=0)
    return Ridge(alpha=1.0)


def walk_forward(P, cfg, lo, hi):
    xc = [f"x_{c}" for c in FEATS]
    forms = sorted(P.loc[(P.form >= lo) & (P.form <= hi), "form"].unique())
    out = []
    model, trained_year = None, None
    for f in forms:
        f = pd.Timestamp(f)
        # retrain at the first formation of each walk-forward year (December formations)
        yr = f.year + (1 if f.month == 12 else 0)
        if model is None or yr != trained_year:
            tr = P[(P.t1 <= f) & P.y.notna()]
            Xt = tr[xc].values
            if cfg["kind"] != "hgb":
                Xt = np.nan_to_num(Xt)
            model = make_model(cfg).fit(Xt, tr.y.values)
            trained_year = yr
            last_model = (model, len(tr))
        te = P[P.form == f]
        Xe = te[xc].values if cfg["kind"] == "hgb" else np.nan_to_num(te[xc].values)
        o = te[["form", "ticker", "ret", "ended", "is500", "mom12_1", "t0", "t1", "n_mem", "n_nodata", "n_nodata_exit", "spy_ret"]].copy()
        o["score"] = model.predict(Xe)
        out.append(o)
    return pd.concat(out, ignore_index=True), model


def rank_ic(S, col):
    ic = S.groupby("form").apply(lambda g: g[col].corr(g["ret"], method="spearman"))
    return ic


def ic_stats(ic):
    ic = ic.dropna()
    return dict(mean=ic.mean(), t=ic.mean() / ic.std() * np.sqrt(len(ic)), hit=(ic > 0).mean(), n=len(ic))


def backtest(S, col, k=K, cost_mult=1.0, scen="drop", ended="last"):
    """Top-k equal weight by `col`. Returns monthly DataFrame indexed by holding end (t1).
    scen: missing-member imputation. Members with no price data at formation (the survivorship
    hole) get expected weight q = n_nodata/n_mem (random-selection rate). 'drop' ignores them;
    'neutral' = they earn the EW universe return; 'x50'/'x100' = those that leave the index during
    the holding month (their delisting month) lose 50%/100%, the rest earn the EW return. ended: 'last' = exit at last available price when a series stops
    inside the holding window; 'm50'/'m100' = such holdings lose 50%/100%."""
    rows = []
    prev = pd.Series(dtype=float)
    for f, g in S.groupby("form"):
        g = g.dropna(subset=["ret"])
        if col == "__ew__":
            top = g
        else:
            top = g.nlargest(k, col)
        kk = len(top)
        r = top["ret"].copy()
        if ended != "last":
            r[top["ended"].values] = -0.5 if ended == "m50" else -1.0
        q = g["n_nodata"].iloc[0] / g["n_mem"].iloc[0] if scen != "drop" else 0.0
        w_real = 1 - q
        ew = g["ret"].mean()
        fx = g["n_nodata_exit"].iloc[0] / max(g["n_nodata"].iloc[0], 1)
        fx = 0.0 if not np.isfinite(fx) else fx
        r_miss = {"drop": 0.0, "neutral": ew, "x50": (1 - fx) * ew - 0.5 * fx,
                  "x100": (1 - fx) * ew - 1.0 * fx}[scen]
        gross = w_real * r.mean() + q * r_miss
        c = np.where(top["is500"].values > 0.5, COST500, COST400) * cost_mult
        w_new = pd.Series(w_real / kk, index=top.ticker.values)
        cost_s = pd.Series(c, index=top.ticker.values)
        allk = w_new.index.union(prev.index)
        dw = (w_new.reindex(allk, fill_value=0) - prev.reindex(allk, fill_value=0)).abs()
        cc = cost_s.reindex(allk).fillna(COST400 * cost_mult)
        tc = (dw * cc).sum() + 2 * q * COST400 * cost_mult
        drift = w_new * (1 + r.values)
        prev = drift / drift.sum() * w_real if drift.sum() > 0 else w_new
        rows.append(dict(form=f, t1=g["t1"].iloc[0], t0=g["t0"].iloc[0], gross=gross, cost=tc,
                         net=gross - tc, turnover=dw.sum(), spy=g["spy_ret"].iloc[0],
                         hold=",".join(top.ticker.values) if col != "__ew__" else "",
                         frac500=top["is500"].mean()))
    return pd.DataFrame(rows).set_index("t1")


# ---- SPY trend switch (deep_trend_switch style), reusing m01's defense sleeve (read-only) ----
def trend_overlay(bt, cost_mult=1.0):
    C = pd.read_pickle(DATA / "close.pkl")["SPY"].dropna().astype(float)
    lp = np.log(C)
    up = sum(((lp - lp.shift(L)) > 0).astype(float) for L in (126, 168, 210, 252)) / 4
    u = up.reindex(bt["form"].values).values
    dd = pd.read_csv(M01 / f"defense_daily_x{1 if cost_mult == 1 else 2}.csv", parse_dates=["date"],
                     index_col="date").iloc[:, 0]
    eq = (1 + dd).cumprod()
    dfn = np.array([eq.loc[:b.Index].iloc[-1] / eq.loc[:b.t0].iloc[-1] - 1 for b in bt.itertuples()])
    du = np.abs(np.diff(np.r_[u[0], u]))
    net = u * bt["net"].values + (1 - u) * dfn - du * (0.0008 * cost_mult + 0.0003 * cost_mult)
    return pd.Series(net, index=bt.index), pd.Series(u, index=bt.index)


def summ(r, spy, label):
    yrs = len(r) / 12
    c, cs = cagr_m(r), cagr_m(spy)
    return dict(label=label, cagr=c, spy=cs, excess=c - cs, maxdd=maxdd(r), vol=r.std() * np.sqrt(12),
                sharpe_ish=r.mean() / r.std() * np.sqrt(12), months=len(r))


def run(period, names):
    P, months = load()
    lo, hi = DEV if period == "dev" else TEST
    res, ics, allS = [], {}, {}
    for name in names:
        t = time.time()
        S, model = walk_forward(P, CONFIGS[name], lo, hi)
        S.to_parquet(DATA / f"scores_{period}_{name}.parquet")
        allS[name] = S
        ic = rank_ic(S, "score")
        ics[name] = ic
        st = ic_stats(ic)
        bt = backtest(S, "score")
        bt.to_csv(OUT / f"bt_{period}_{name}.csv")
        s = summ(bt["net"], bt["spy"], name)
        s.update(ic_mean=st["mean"], ic_t=st["t"], ic_hit=st["hit"], secs=round(time.time() - t))
        res.append(s)
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}, flush=True)
    S0 = allS[names[0]]
    ics["mom12_1"] = rank_ic(S0, "mom12_1")
    pd.DataFrame(ics).to_csv(OUT / f"ic_{period}.csv")
    st = ic_stats(ics["mom12_1"])
    bm = backtest(S0, "mom12_1"); bm.to_csv(OUT / f"bt_{period}_mom12_1.csv")
    be = backtest(S0, "__ew__"); be.to_csv(OUT / f"bt_{period}_ew.csv")
    s = summ(bm["net"], bm["spy"], "ctrl_mom12_1_top25"); s.update(ic_mean=st["mean"], ic_t=st["t"], ic_hit=st["hit"])
    res.append(s)
    res.append(summ(be["net"], be["spy"], "ctrl_ew_universe"))
    res.append(summ(bm["spy"], bm["spy"], "ctrl_spy"))
    R = pd.DataFrame(res)
    R.to_csv(OUT / f"results_{period}.csv", index=False)
    log = R.assign(run_at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), period=period,
                   note=os.environ.get("M11_NOTE", ""))
    lf = OUT / "configs_log.csv"
    log.to_csv(lf, mode="a", header=not lf.exists(), index=False)
    print(R.round(4).to_string())
    return R, allS, ics


if __name__ == "__main__":
    period = sys.argv[1]
    if period == "dev":
        names = sys.argv[2:] or list(CONFIGS)
        run("dev", names)
    else:
        assert (OUT / "PREREG.md").exists(), "write PREREG.md first"
        run("test", sys.argv[2:])
