# Round 5/5b/6 results tracker (orchestrator)

| agent | idea | verdict | DEV | TEST (sealed, run once) | notes |
|---|---|---|---|---|---|
| m02 | crypto cross-sectional momentum + BTC filter | **NO EDGE** | 68.1% vs BTC 36.4% (2018–21) | **−41.9%** vs BTC +11.3%, SPY +12.2% (2022–08/2026) | DEV edge not significant (t=0.58) and parameter-fragile (20–113%); 2021 mania drove it. In TEST, winners reverse (top-5 minus top-30 = −0.97%/week, t=−2.2). Costs only 2.6 pts. Capacity ~$1–5M even in DEV. |
| m03 | convex trend with long SPX calls | NO EDGE (dev) | best 9.3% vs SPY ~10.3% (1990–2007) | not run | see INTERIM_m03_m04.md |
| m04 | Noah-effect tail barbell (97% SPX + 3% OTM puts) | **NO EDGE** | pre-registered 10.03% vs SPY 10.27% (1990–2007); 0 of 24 configs beat SPY | **11.17% vs 11.37%** (2008–26); 0 of 24 configs beat SPY; 2× spread −0.24; SSVI −0.22 | Puts pay 63–168× in crashes, but a pre-set sell rule only recovers the premium bleed. Real Cboe VXTH also lags the S&P TR by −1.4 pts/yr. Perfect-hindsight bound is +8 pts/yr. Pricer checked against a real chain and against PPUT (0.99 correlation). |
