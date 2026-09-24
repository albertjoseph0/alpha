"""Analysis stage 1: build (market, horizon) decision snapshots for Kalshi and Polymarket.

usage: a01_snapshots.py DEV|TEST
Output: snap_kalshi_<PER>.csv.gz, snap_poly_<PER>.csv.gz  (one row per market x horizon H, hours)

Timing (no lookahead):
  d        = decision time = anchor - H  (Kalshi anchor = scheduled close_time; Polymarket anchor = endDate)
  signal   = last bar with end <= d - 1h  -> which side leads (mid >= 0.5 -> YES)
  execution= last bar with end <= d       -> tradeable price of the leading side
             Kalshi:     YES ask = yes_ask_close ; NO ask = 1 - yes_bid_close (real quotes only)
             Polymarket: hourly price (mid/last) of the leading outcome; slippage added in the analysis
  hold     = d -> settlement (Kalshi settlement_ts ; Polymarket closedTime)
Also stored: quote age, spread, 24h prior volume (Kalshi), discovery flag (Kalshi market seen on the
trade tape at a random sampling time <= d), on-schedule flag (Kalshi close at the series' modal local
clock time, i.e. not an early close).
"""
import gzip
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from http_cache import ROOT  # noqa

D = os.path.join(ROOT, "data/round5/m07_prediction_markets")
per = sys.argv[1]
HS = [1, 2, 4, 8, 12, 24, 48, 72]


def last_idx(t, x):
    """index of last element of sorted t with t <= x, or -1"""
    return int(np.searchsorted(t, x, side="right")) - 1


# ---------------------------------------------------------------- Kalshi
def kalshi():
    s = pd.read_csv(os.path.join(D, f"kalshi_sample_{per}.csv.gz"))
    with gzip.open(os.path.join(D, f"kalshi_candles_{per}.pkl.gz"), "rb") as f:
        C = pickle.load(f)
    s = s[s.ticker.isin(C.keys())].copy()
    # on-schedule: close local clock time (US/Eastern) equals the series' modal local clock time
    loc = pd.to_datetime(s.close_time, utc=True, format="ISO8601").dt.tz_convert("America/New_York").dt.strftime("%H:%M")
    s["close_hm"] = loc
    mode = s.groupby("series").close_hm.agg(lambda x: x.value_counts().index[0])
    nser = s.groupby("series").size()
    s["on_sched"] = (s.close_hm.values == s.series.map(mode).values) & (s.series.map(nser).values >= 5)
    disc = pd.read_csv(os.path.join(D, "kalshi_discovery.csv.gz"))
    disc = disc[disc.period == per]
    dmap = {k: np.sort(v.values) for k, v in disc.groupby("ticker").disc_ts}
    rows = []
    for r in s.itertuples():
        a = C[r.ticker]
        if len(a) == 0:
            continue
        t, bid, ask, px, vol = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]
        dts = dmap.get(r.ticker, np.array([]))
        for H in HS:
            d = r.anchor_ts - H * 3600
            if d <= r.open_ts + 3600:
                continue
            i_s = last_idx(t, d - 3600)
            i_e = last_idx(t, d)
            if i_s < 0 or i_e < 0:
                continue
            b_s, a_s = bid[i_s], ask[i_s]
            if b_s > 0 and a_s < 1:
                mid = (b_s + a_s) / 2
            elif not np.isnan(px[:i_s + 1]).all():
                mid = px[:i_s + 1][~np.isnan(px[:i_s + 1])][-1]
            else:
                continue
            lead_yes = mid >= 0.5
            be, ae = bid[i_e], ask[i_e]
            if lead_yes:
                p = ae if (0 < ae < 1) else np.nan
                pmid = (be + ae) / 2 if be > 0 and ae < 1 else np.nan
            else:
                p = 1 - be if (0 < be < 1) else np.nan
                pmid = 1 - (be + ae) / 2 if be > 0 and ae < 1 else np.nan
            v24 = np.nansum(vol[(t > d - 86400) & (t <= d)])
            res = r.result
            yes_pay = 1.0 if res == "yes" else (0.0 if res == "no" else np.nan)
            rows.append(dict(
                venue="kalshi", mkt=r.ticker, event=r.event_ticker, series=r.series, category=r.category,
                H=H, d=int(d), settle_ts=int(r.settle_ts), lead_yes=bool(lead_yes), sig_mid=float(mid),
                p=float(p), pmid=float(pmid), age_h=(d - t[i_e]) / 3600, v24=float(v24),
                pay=(yes_pay if lead_yes else 1 - yes_pay), result=res,
                disc_ok=bool(len(dts) and dts[0] <= d), on_sched=bool(r.on_sched),
                can_close_early=bool(r.can_close_early), fee_mult=1.0,
            ))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(D, f"snap_kalshi_{per}.csv.gz"), index=False)
    print("kalshi snapshots", len(out), "markets", out.mkt.nunique(), flush=True)


# ---------------------------------------------------------------- Polymarket
def poly():
    s = pd.read_csv(os.path.join(D, f"poly_sample_{per}.csv.gz"), low_memory=False, dtype={"id": str, "event_id": str})
    with gzip.open(os.path.join(D, f"poly_hist_{per}.pkl.gz"), "rb") as f:
        P = {str(k): v for k, v in pickle.load(f).items()}
    s = s[s.id.isin(P.keys())].copy()
    st = pd.to_datetime(s.startDate, utc=True, errors="coerce", format="ISO8601")
    s["life_d"] = ((s.closed_ts - (st - pd.Timestamp(0, tz="UTC")).dt.total_seconds()) / 86400).clip(lower=1).fillna(30)
    rows = []
    for r in s.itertuples():
        a = P[r.id]
        if len(a) == 0:
            continue
        t, p0 = a[:, 0], a[:, 1]
        try:
            op = [float(x) for x in json.loads(r.outcomePrices)]
        except Exception:
            op = [np.nan, np.nan]
        for H in HS:
            d = r.anchor_ts - H * 3600
            if d >= r.closed_ts:          # already closed at decision time -> not tradeable
                continue
            i_s = last_idx(t, d - 3600)
            i_e = last_idx(t, d)
            if i_s < 0 or i_e < 0:
                continue
            lead0 = p0[i_s] >= 0.5
            p = p0[i_e] if lead0 else 1 - p0[i_e]
            pay = op[0] if lead0 else op[1]
            rows.append(dict(
                venue="poly", mkt=str(r.id), event=str(r.event_id), series=str(r.series_slug), category=str(r.category),
                H=H, d=int(d), settle_ts=int(r.closed_ts), lead_yes=bool(lead0), sig_mid=float(p0[i_s]),
                p=float(p), pmid=float(p), age_h=(d - t[i_e]) / 3600, v24=np.nan, vol_total=r.volumeNum,
                life_d=r.life_d, pay=pay, result=r.outcomePrices, uma=r.umaResolutionStatus, neg_risk=r.negRisk,
            ))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(D, f"snap_poly_{per}.csv.gz"), index=False)
    print("poly snapshots", len(out), "markets", out.mkt.nunique(), flush=True)


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "both"
    if which in ("both", "kalshi"):
        kalshi()
    if which in ("both", "poly"):
        poly()
