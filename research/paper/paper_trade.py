"""Forward paper trading of a harness strategy (no real orders are placed).

    .venv/bin/python research/paper/paper_trade.py [--refresh] [--strategy strategies/deep_trend_switch/strategy.py]

Each run:
  1. (optionally) refreshes the ETF universe prices,
  2. marks the paper book to market with total-return (adjusted-close) returns since the last run,
     and marks a SPY buy-and-hold benchmark book the same way,
  3. asks the strategy for its latest target (same code path as the backtest and harness.live), and when
     the strategy has set a NEW target, trades the book to it at the latest close, paying the harness's
     per-ETF cost (bp of traded notional),
  4. appends NAV rows to research/paper/nav.csv and trades to research/paper/trades.csv, and saves the state to
     research/paper/state.json.
Positions are held as dollar values that compound with each ETF's daily total return. Cash earns nothing
(conservative). Start capital is $100,000.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.__main__ import load_strategy  # noqa: E402
from harness.data import load_etf, etf_meta  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
STATE, NAV, TRADES = HERE / "state.json", HERE / "nav.csv", HERE / "trades.csv"
START_CAPITAL = 100_000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="strategies/deep_trend_switch/strategy.py")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.refresh:
        subprocess.run([sys.executable, str(ROOT / "data" / "fetch_etf_universe.py")], check=True,
                       stdout=subprocess.DEVNULL)
    data = load_etf()
    R = data.returns
    last = R.index[-1]
    costs = etf_meta()["cost_bps"] if "cost_bps" in etf_meta() else pd.Series(5.0, index=R.columns)

    if STATE.exists():
        st = json.loads(STATE.read_text())
    else:
        st = {"strategy": a.strategy, "asof": None, "cash": START_CAPITAL, "pos": {},
              "spy": START_CAPITAL, "target_set_on": None, "inception": str(last.date())}

    # 1) mark to market from the day after the last mark through the latest close
    if st["asof"] is not None:
        days = R.index[R.index > pd.Timestamp(st["asof"])]
        for d in days:
            r = R.loc[d].fillna(0.0)
            st["pos"] = {t: v * (1 + float(r.get(t, 0.0))) for t, v in st["pos"].items()}
            st["spy"] *= 1 + float(r.get("SPY", 0.0))
    st["asof"] = str(last.date())

    # 2) latest strategy target (same code as harness.live)
    strat = load_strategy(a.strategy)
    strat.fit(data)
    w = strat.predict(data, data.dates[-80:]).dropna(how="all")
    set_on = w.index[-1]
    target = w.loc[set_on].fillna(0.0)
    target = target[target > 1e-6]

    nav = st["cash"] + sum(st["pos"].values())
    trades = []
    if st["target_set_on"] != str(set_on.date()):
        cur = pd.Series(st["pos"], dtype=float)
        tgt_val = (target * nav).reindex(cur.index.union(target.index)).fillna(0.0)
        delta = tgt_val - cur.reindex(tgt_val.index).fillna(0.0)
        cost = float((delta.abs() * costs.reindex(delta.index).fillna(10.0) / 1e4).sum())
        for t, dv in delta.items():
            if abs(dv) > 1.0:
                trades.append({"date": str(last.date()), "ticker": t, "dollars": round(float(dv), 2)})
        nav_after = nav - cost
        st["pos"] = {t: float(v) * nav_after / nav for t, v in tgt_val.items() if v > 1.0}
        st["cash"] = nav_after - sum(st["pos"].values())
        st["target_set_on"] = str(set_on.date())
        nav = nav_after
    json_state = json.dumps(st, indent=1)
    STATE.write_text(json_state)

    row = pd.DataFrame([{"date": st["asof"], "nav": round(nav, 2), "spy_nav": round(st["spy"], 2),
                         "target_set_on": st["target_set_on"], "n_trades": len(trades)}])
    if NAV.exists():
        old = pd.read_csv(NAV)
        old = old[old["date"] != st["asof"]]
        row = pd.concat([old, row])
    row.to_csv(NAV, index=False)
    if trades:
        tdf = pd.DataFrame(trades)
        if TRADES.exists():
            tdf = pd.concat([pd.read_csv(TRADES), tdf])
        tdf.to_csv(TRADES, index=False)

    print(f"paper book {strat.name}: as of {st['asof']}, NAV ${nav:,.0f} vs SPY book ${st['spy']:,.0f} "
          f"(since {st['inception']}); target set on {st['target_set_on']}; trades this run: {len(trades)}")
    for t, v in sorted(st["pos"].items(), key=lambda x: -x[1]):
        print(f"  {t:6s} ${v:>10,.0f}  {v / nav:6.1%}")


if __name__ == "__main__":
    main()
