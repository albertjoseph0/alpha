"""Research lab: monthly top-third equal-weight momentum on the 49 industries with pluggable signals.
Not the deliverable (see strategy.py)."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np, pandas as pd
from harness import Strategy, I49, INDUSTRIES

# a-priori mapping of the FF49 industries onto the FF12 groups (by SIC definitions)
GROUP = {
    "NoDur": ["Agric", "Food", "Soda", "Beer", "Smoke", "Toys", "Hshld", "Clths", "Txtls"],
    "Durbl": ["Autos"],
    "Manuf": ["Rubbr", "BldMt", "Steel", "FabPr", "Mach", "ElcEq", "Aero", "Ships", "Guns", "Paper", "Boxes"],
    "Enrgy": ["Coal", "Oil"], "Chems": ["Chems"],
    "BusEq": ["Hardw", "Softw", "Chips", "LabEq"], "Telcm": ["Telcm"], "Utils": ["Util"],
    "Shops": ["Whlsl", "Rtail", "Meals", "PerSv"], "Hlth": ["Hlth", "MedEq", "Drugs"],
    "Money": ["Banks", "Insur", "RlEst", "Fin"],
    "Other": ["Books", "Fun", "Cnstr", "Gold", "Mines", "Trans", "BusSv", "Other"],
}
G_OF = {f"i49_{s}": g for g, subs in GROUP.items() for s in subs}
assert sorted(G_OF) == sorted(I49)


def xrank(df):
    return df.rank(axis=1, pct=True)


def mom(lp, a, b):
    return lp.shift(a) - lp.shift(b)


def signal(name, R, Rall):
    """Return score frame (higher = buy). R: i49 returns, Rall: all tradeable returns."""
    L = np.log1p(R.fillna(0.0))
    lp = L.cumsum()
    if name == "base":
        return mom(lp, 21, 252)
    if name == "ens_6_9_12":
        return (xrank(mom(lp, 21, 126)) + xrank(mom(lp, 21, 189)) + xrank(mom(lp, 21, 252))) / 3
    if name == "ens_6_9_12_noskip":
        return sum(xrank(mom(lp, s, n)) for s in (0, 21) for n in (126, 189, 252)) / 6
    if name == "ens_3_12":
        return sum(xrank(mom(lp, 21, n)) for n in (63, 126, 189, 252)) / 4
    if name == "mom12_0":
        return mom(lp, 0, 252)
    if name == "mom12_7":
        return mom(lp, 126, 252)
    if name == "high52":
        return lp - lp.rolling(252).max()
    if name == "volscaled":
        return mom(lp, 21, 252) / L.rolling(252).std()
    if name.startswith("resid"):
        Lm = np.log1p(Rall["Mkt"].fillna(0.0)); lpm = Lm.cumsum()
        r21 = lp.diff(21); m21 = lpm.diff(21)
        beta = r21.rolling(756, min_periods=504).cov(m21).div(m21.rolling(756, min_periods=504).var(), axis=0)
        res = mom(lp, 21, 252) - beta.mul(mom(lpm, 21, 252), axis=0)
        if name == "resid":
            return res
        if name == "resid_ens":  # half raw, half residual rank
            return xrank(res) + xrank(mom(lp, 21, 252))
    if name == "smooth":  # rank(mom) + rank(fraction of days in the direction of the move): frog-in-the-pan
        m = mom(lp, 21, 252)
        pos = (L > 0).astype(float).rolling(231).mean().shift(21)
        neg = (L < 0).astype(float).rolling(231).mean().shift(21)
        idisc = np.sign(m) * (neg - pos)  # low = continuous
        return xrank(m) + xrank(-idisc)
    if name == "group":
        lpg = np.log1p(Rall[INDUSTRIES].fillna(0.0)).cumsum()
        gm = mom(lpg, 21, 252)
        g = pd.DataFrame({c: gm[G_OF[c]] for c in R.columns}, index=R.index)
        return xrank(mom(lp, 21, 252)) + xrank(g)
    raise ValueError(name)


class Lab(Strategy):
    refit_every = None

    def __init__(self, sig, frac=1/3):
        self.sig, self.frac = sig, frac
        self.name = f"lab:{sig}"

    def predict(self, data, dates):
        Rall = data.tradeable_returns()
        R = Rall[I49]
        S = signal(self.sig, R, Rall) if isinstance(self.sig, str) else self.sig(R, Rall)
        valid = R.notna().rolling(252).sum() >= 250
        cal = data.dates; pos = cal.get_indexer(dates)
        first = dates.month != np.where(pos > 0, cal[np.maximum(pos - 1, 0)].month, -1)
        out = pd.DataFrame(np.nan, index=dates, columns=I49)
        for d in dates[first]:
            m = S.loc[d].where(valid.loc[d]).dropna()
            k = max(1, int(round(len(m) * self.frac)))
            top = m.nlargest(k).index
            out.loc[d] = 0.0; out.loc[d, top] = 1.0 / k
        return out
