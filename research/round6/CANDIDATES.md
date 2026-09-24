# Round 6 candidates (drafted while round 5b runs; finalized after its results)

Selection rule: same bar as round 5. Each idea needs published evidence of a large effect, a mechanism that
survives publication (capacity limits, forced trading, or information that is costly to process), a long-only
or bounded-downside implementation, and free data this container can reach. Where text needs reading, Jev
(TypeSafe, via research/round5/jev.py) is the extractor, and all prediction happens in a model trained on DEV.

| id | idea | evidence | data | where Jev comes in | notes |
|---|---|---|---|---|---|
| c1 | **"Lazy Prices": 10-K/10-Q change signal.** Avoid firms whose annual/quarterly report language changed materially. Hold "non-changers", long-only. | Cohen, Malloy & Nguyen (JF 2020): changers underperform by ~188bp/month (long-short) over the following months; the effect is slow and largely unarbitraged. | EDGAR full-text filings (reachable); prices from yfinance plus point-in-time membership (m06/m11). | Jev compares the Risk Factors and MD&A sections year on year: new risks, removed guidance, litigation, going-concern language, and so on. Plain cosine similarity is the baseline. | The strongest text-based candidate; directly extends m06. |
| c2 | **13F "best ideas" cloning.** Buy the highest-conviction holding (largest overweight vs the market) of concentrated, skilled managers. | Cohen, Polk & Silli, "Best Ideas" (2010): managers' top ideas beat the market by ~1.2–1.9%/month; the rest of their holdings don't. | SEC 13F structured data sets (2013+) and older 13F-HR filings on EDGAR. | Not needed (structured). | The 45-day filing lag must be handled; capacity is large. |
| c3 | **Spin-offs with Jev-read Form 10s.** Greenblatt's conditions as pre-registered filters. | Cusatis et al. 1993; Greenblatt. | m08's EDGAR data (efts hits and Form 10 list already fetched). | Stated reasons, management equity grants, debt-funded payout to the parent, industry mismatch. | Small N (~800 events), so no free-form learning. |
| c4 | **Prediction-market favourite–longshot** (round-5 m07, never run). | Favourite–longshot bias literature. | Kalshi and Polymarket APIs (reachable; m07 cached some candles). | Optional: classify market type and resolution-risk wording. | Tiny capacity but high return on capital; clean, fast test. |
| c5 | **Barbell + trend switch.** If m04 finds the barbell ≥ SPY, combine the put overlay with deep_trend_switch. | m04 result pending. | m04 pricer. | — | Conditional on m04. |
| c6 | **Stock-level residual momentum + quality**, long-only with the trend switch. | Blitz, Huij & Martens (2011); quality momentum. | m11 features. | Optional: Jev-scored 10-K business-quality questions. | Conditional on m01 and m11 results. |
| c7 | **Short-interest avoidance filter** on any long book. | Heavily shorted stocks underperform (Boehmer, Jones & Zhang 2008; Rapach et al. 2016). | FINRA short interest (bi-monthly) and daily short volume (m11 fetches). | — | An add-on to c6 or m01, not standalone. |
| c8 | **Crypto funding squeeze and post-listing drift** (round-5 m09, partial). | Crowding literature. | m09's Binance funding data (already fetched). | — | Only if m02 shows crypto signals survive costs. |

Launch policy for round 6:
* At most 4–5 agents at once (4 CPUs).
* Every agent keeps STATUS.md.
* Pre-registration and a sealed TEST for every idea.
* Jev budgets set per agent. Account balance ~$55 at the start of round 5b.
