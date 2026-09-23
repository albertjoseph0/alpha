from simlib import *
from harness import INDUSTRIES
d = load_dev()
R = d.returns[INDUSTRIES]
res = {}
def show(name, W):
    res[name] = [round(sim(W, d, w)[0], 4) for w in ["dev", "dev_a", "dev_b"]]
# monthly rebalance marker
month_end = R.index.to_series().dt.to_period("M")
first = ~month_end.duplicated(keep="last")
ew = pd.DataFrame(1/12, index=R.index, columns=INDUSTRIES)
show("EW daily", ew)
show("EW monthly", ew.where(first))
for hl in [21, 63, 126]:
    v = (R**2).ewm(halflife=hl, min_periods=hl).mean()
    iv = 1/np.sqrt(v); iv = iv.div(iv.sum(1), axis=0)
    ivar = 1/v; ivar = ivar.div(ivar.sum(1), axis=0)
    show(f"invvol hl{hl} monthly", iv.where(first))
    show(f"invvar hl{hl} monthly", ivar.where(first))
print(pd.DataFrame(res, index=["dev", "dev_a", "dev_b"]).T)
# industry CAGRs by half
for win in ["dev_a", "dev_b"]:
    s, e = WIN[win]
    x = np.log1p(R[s:e]).mean()*252
    print(win, (np.expm1(x)).round(3).to_dict())
