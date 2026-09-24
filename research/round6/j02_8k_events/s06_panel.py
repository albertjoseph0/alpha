"""Merge events, returns/price features, text features and Jev answers into one panel.
Usage: s06_panel.py VERSION -> DATA/panel_<VERSION>.parquet"""
import sys
import numpy as np, pandas as pd
from common import DATA, ITEMS, read_texts


def jev_flat(a):
    d = {}
    for k, v in a.items():
        t = v.get("type")
        if t == "noul":
            d["j_" + k] = v["noul"]
        elif t == "score":
            p = v["probabilities"]
            d["j_" + k] = sum(int(i) * float(x) for i, x in p.items())  # expected level (0-based)
            d["jc_" + k] = v.get("confidence", np.nan)
        elif t == "choice":
            for c, x in v["probabilities"].items():
                d[f"j_{k}_{c}"] = x
            d["jc_" + k] = v.get("confidence", np.nan)
            d["jch_" + k] = v.get("choice")
    return d


def build(ver):
    ev = pd.read_csv(DATA / "events_8k.csv", parse_dates=["filingDate", "accept_et"])
    R = pd.read_parquet(DATA / "event_returns.parquet")
    F = pd.read_parquet(DATA / "textfeat.parquet")
    P = ev.rename(columns={"accessionNumber": "acc"}).merge(R, on="acc", how="left").merge(F, on="acc", how="left")
    P["n_items"] = P["items"].str.count(",") + 1
    P["hour"] = P.accept_et.dt.hour + P.accept_et.dt.minute / 60
    P["after_hours"] = ((P.hour >= 16) | (P.hour < 9.5)).astype(int)
    if ver:
        J = pd.DataFrame([{"acc": r["acc"], "nstate": r["nstate"], **jev_flat(r["a"])} for r in read_texts(DATA / f"jev_{ver}.jsonl.gz")])
        P = P.merge(J, on="acc", how="left")
    return P


if __name__ == "__main__":
    ver = sys.argv[1] if len(sys.argv) > 1 else ""
    P = build(ver)
    P.to_parquet(DATA / f"panel_{ver or 'base'}.parquet")
    print(P.shape, P.filter(like="j_").notna().any(axis=1).sum())
