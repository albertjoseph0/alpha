# CAGR harness

One metric, one code path, identical frictions for every strategy.

```bash
.venv/bin/python -m harness strategies/<name>/strategy.py              # dev CAGR
.venv/bin/python -m harness strategies/<name>/strategy.py --benchmarks # + reference CAGRs
.venv/bin/python -m harness strategies/<name>/strategy.py --window dev_a   # 1950-74 half
.venv/bin/python -m pytest -q tests/                                    # harness self-tests
```

## The metric

**CAGR** = (final equity / initial equity)^(1 / years) − 1, where *years* runs from the
close before the first scored day to the last scored close (calendar days / 365.25).
If equity ever hits 0, CAGR = −100%. Nothing else is scored.

## Data (`data/market_daily.csv`, Kenneth R. French Data Library)

Daily total returns 1926-07-01 → 2026-07-31. Tradeable: `Mkt` (US total market,
CRSP value-weighted) plus 12 value-weighted industry portfolios
(`NoDur Durbl Manuf Enrgy Chems BusEq Telcm Utils Shops Hlth Money Other`).
Cash earns `RF` (1-month T-bill). Rebuild with `python data/fetch_data.py`.

## Windows

| window | scored period | who may run it |
|---|---|---|
| `dev` | 1950-01-01 → 1999-12-31 | everyone; the official development score |
| `dev_a` / `dev_b` | 1950–1974 / 1975–1999 | everyone; for internal validation |
| `holdout` | 2000-01-01 → end of data | **orchestrator only** (needs `ALPHA_HOLDOUT=1`) |

Data before a window's start is available to `fit()`, walking forward. For research,
use `harness.load_dev()` (ends 1999-12-31). Never look at post-1999 data.

## Rules the engine enforces

| rule | value | why |
|---|---|---|
| execution lag | decide at close *t*, trade at close *t+1*, earn from *t+2* | old index data has strong stale-price autocorrelation (lag-1 ≈ +0.29 in the 1970s). With no lag, "buy if yesterday was up" scores 28% CAGR in 1950–99 and −20% after 2000. With the lag it has no edge. |
| costs | 5 bp × one-way turnover (vs. drifted weights) | every rebalance pays |
| leverage | Σ\|w\| ≤ 1; shorts allowed; excess rows scaled down | stops CAGR from being bought with leverage |
| cash | 1 − Σw earns the T-bill rate | |
| NaN row | "no trade": positions drift | |

## Writing a strategy

```python
from harness import Strategy, MarketData
import pandas as pd

class MyStrategy(Strategy):
    name = "family:my_strategy"
    refit_every = 252          # decision days between fit() calls; None = fit once

    def fit(self, data: MarketData) -> None:          # data ends at the refit date
        ...

    def predict(self, data: MarketData, dates: pd.DatetimeIndex) -> pd.DataFrame:
        ...  # rows = dates, columns ⊆ harness.ASSETS, row d uses data <= d only
```

`MarketData` has `.returns` (DataFrame), `.rf`, `.prices()`, `.log_returns()`, `.until(date)`.

**Causality audit.** Within each block of up to 252 days, the runner re-calls
`predict(data.until(d), [d])` for sampled dates (always the block's first) and
requires the same weights (tol 1e-5). Any use of later data inside a block fails with
`LookaheadError`. Therefore: `predict` must be a deterministic, pure function of
(fitted state, data ≤ d). Put all learning in `fit`, seed all randomness, and compute
features in a batch-invariant way (e.g. float64, no normalisation over the whole
`data` window).

## Reference CAGRs

| benchmark | dev 1950–1999 |
|---|---:|
| buy & hold `Mkt` | +13.40% |
| equal-weight 12 industries, monthly | +13.54% |
| cash (T-bills) | +5.15% |
