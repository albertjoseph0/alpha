from simlib import *
d = load_dev()
r = d.returns["Mkt"]
out = []
for hl in [10, 21, 63]:
    v = (r**2).ewm(halflife=hl, min_periods=hl).mean() * 252
    for c in [0.02, 0.03, 0.04, 0.06]:
        w = np.minimum(1.0, c / v)
        row = [hl, c] + [sim(pd.DataFrame({"Mkt": w}), d, win)[0] for win in ["dev", "dev_a", "dev_b"]]
        row.append(float(w["1950":"1999"].mean()))
        out.append(row)
print(pd.DataFrame(out, columns=["hl", "c", "dev", "dev_a", "dev_b", "avg_w"]).round(4))
print("B&H", [round(sim(pd.DataFrame({"Mkt": pd.Series(1.0, index=d.dates)}), d, w)[0], 4) for w in ["dev", "dev_a", "dev_b"]])
