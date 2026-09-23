"""Baselines: buy&hold, trend filters (market / per-industry), cross-sectional momentum."""
from sim import *  # noqa

R = D.returns[ASSETS]
lr = np.log1p(R)
cum = lr.cumsum()
n = len(R)
idx = D.dates
IND = ASSETS[1:]
# monthly anchors: every 21 rows from row 0; weights change only at anchors (then held)
anchor = (np.arange(n) % 21) == 20

def at_anchors(W):
    W = W.copy()
    W[~anchor] = np.nan
    return W.ffill().fillna(0.0)

res = []
def run(label, W):
    o = score(W, label)
    print(fmt(label, o, f"turn/yr {turnover(W):.2f}"), flush=True)

bh = pd.DataFrame(0.0, idx, ASSETS); bh["Mkt"] = 1.0
run("B&H Mkt", bh)
ew = pd.DataFrame(1.0 / 12, idx, ASSETS); ew["Mkt"] = 0.0
run("EW industries (daily rebal target)", at_anchors(ew))
for L in [126, 252]:
    s = (cum - cum.shift(L)) > 0
    W = pd.DataFrame(0.0, idx, ASSETS); W["Mkt"] = s["Mkt"].astype(float)
    run(f"Mkt TSMOM {L}d long/cash monthly", at_anchors(W))
    W = s[IND].astype(float) / 12.0; W["Mkt"] = 0.0
    run(f"Industries TSMOM {L}d each 1/12 long/cash monthly", at_anchors(W[ASSETS]))
ma = np.log(D.prices()[ASSETS]).rolling(200).mean()
s = np.log(D.prices()[ASSETS]) > ma
W = pd.DataFrame(0.0, idx, ASSETS); W["Mkt"] = s["Mkt"].astype(float)
run("Mkt 200dMA daily", W)
run("Mkt 200dMA monthly", at_anchors(W))
# cross-sectional momentum: top 4 industries by 12-1m (skip last month)
mom = (cum.shift(21) - cum.shift(252))[IND]
rk = mom.rank(axis=1, ascending=False)
W = (rk <= 4).astype(float) / 4; W["Mkt"] = 0.0
run("XS mom top4 of 12 (12-1m), monthly", at_anchors(W[ASSETS]))
mom = (cum - cum.shift(252))[IND]
rk = mom.rank(axis=1, ascending=False)
W = (rk <= 4).astype(float) / 4; W["Mkt"] = 0.0
run("XS mom top4 of 12 (12m), monthly", at_anchors(W[ASSETS]))
