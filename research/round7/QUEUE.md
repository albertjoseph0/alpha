# Round 7 launch queue (the concurrent subagent limit is 20; launch in order as slots free up)

**Common header for every queued prompt:** "You are research agent <id> in /home/user/alpha. First read
research/round7/BRIEF_R7.md, research/round5/BRIEF.md and research/round6/BRIEF_JEV.md completely and follow them.
Your folder is research/round7/<id>_<name>/ and your data folder is data/round7/<id>_<name>/. Jev agent id "<id>",
budget $1.50 (non-Jev agents: Jev optional). Keep STATUS.md up to date. Finish with README.md." Then the idea text
below.

Mark an entry `LAUNCHED <time>` when you start it.

## q1: j13_commodity_links (Jev)
Commodity-exposure links. Jev reads 10-K Item 7A/1A commodity-risk text and classifies each of 12
commodities (crude, natgas, fuel, copper, aluminum, steel, gold, silver, corn, wheat, soybeans, lumber) as an input
cost, an output/revenue driver, or not material, with a materiality score. Monthly tailwind = Σ(output − input
exposure) × last month's commodity return (ETF proxies: USO, UNG, CPER, GLD, SLV, CORN, WEAT, SOYB, DBB, WOOD).
Long-only: top quintile, equal-weight, point-in-time S&P 500/400. Nested sets: sector momentum / keyword exposures /
Jev exposures. Leakage probe. DEV 2013–19, TEST 2020+ (sealed, PREREG.md first). Costs 10–20bp, and 2×. Use sec.get.

## q2: j14_wasde (Jev)
Jev reads the USDA WASDE monthly report (Cornell archive usda.library.cornell.edu/concern/publications/3t945q76s;
usda.gov is blocked). It scores ending-stocks, production and demand revisions and a bullish/bearish tone per
commodity. Long-only among CORN, WEAT, SOYB and DBA or cash until the next report. Nested sets: momentum+seasonality /
keyword tone / Jev. Leakage probe. DEV 2011–18, TEST 2019+ (sealed). Costs 5–10bp, and 2×. Benchmarks: SPY and DBA.

## q3: j15_global_cb (Jev)
Non-US central banks (ECB, BoE, BoJ, BoC, RBA; all their sites reachable). Jev scores each statement vs the previous one
for hawkish/dovish shift, growth outlook, inflation concern and guidance change. Long-only tilt among EZU/EWG, EWU,
EWJ, EWC, EWA, SPY and cash. Nested sets: country momentum / dictionary / Jev. Leakage probe. DEV 2000–14, TEST 2015+
(sealed). Few events, so keep the model tiny.

## q4: j16_fed_speeches (Jev)
Fed Board speeches (federalreserve.gov/newsevents/speeches.htm and yearly archives, 1996+). Jev scores stance,
inflation, growth and financial-stability concern, and a change of stance. Weekly tone index, with the Chair and
voters weighted more. Long-only SPY/TLT/IEF/SHY/GLD allocation. Nested sets: trend / dictionary / Jev. Leakage probe.
DEV 1998–2012, TEST 2013+ (sealed). At most ~1,500 speeches, each truncated to ~6k tokens.

## q5: j17_risk_diffusion (Jev)
Industry-level new-risk diffusion. Diff 10-K Item 1A headings vs the prior year in code. Jev classifies the new
risks into ~12 themes with severity. Aggregate by sector into monthly new-risk intensity and hold the 4 sector SPDRs
with the lowest rising risk. Nested sets: sector momentum / cosine change by sector / Jev. Leakage probe. DEV
2013–19, TEST 2020+ (sealed). Sample ~300 firms a year.

## q6: j18_midsmall_earnings (Jev)
Agent m06's method (earnings releases → Jev factual features → model → drift) applied to S&P 400 mid caps, where
analyst coverage is thinner and under-reaction larger. Reuse m06's code read-only (research/round5/m06_filing_reader/)
and the S&P 400 point-in-time membership (data/round5/m01_midcap_momentum/membership_monthly.csv). Nested sets: price
only / Loughran–McDonald / + Jev. Leakage probe. DEV 2013–19, TEST 2020+ (sealed). Costs 10–20bp, and 2×.

## q7: j19_biotech_events (Jev)
Biotech and pharma 8-Ks and press releases (EX-99) about FDA approvals, complete response letters, trial
readouts and label decisions. Jev classifies the event type, direction, label breadth vs expectations stated
in the text, and commercial significance. Long-only: buy after positive events, holding 20–120 days. The universe is
XBI/IBB constituents (current lists plus survivorship bounds) or all SIC 2834/2836 firms with prices. Nested sets: event
type only / keywords / Jev. Leakage probe. DEV 2014–19, TEST 2020+ (sealed). Costs 20–40bp, and 2×.

## q8: j20_red_flags_overlay (Jev)
A red-flag exclusion screen used as an overlay. Jev reads NT 10-K/NT 10-Q late-filing notices, 8-K Item 4.01
auditor changes, Item 4.02 non-reliance, and going-concern language. Build a rolling 12-month "red flag" list and remove
those names from (a) the equal-weight S&P 500/400 universe and (b) a 12-1 momentum top-quintile book. Measure the
incremental CAGR vs the same books without the overlay. Nested sets: form-type flags only / keywords / Jev severity.
Leakage probe. DEV 2013–19, TEST 2020+ (sealed).

## q9: j21_treasury_refunding (Jev)
US Treasury Quarterly Refunding statements and policy statements (home.treasury.gov quarterly-refunding pages,
2000s+). Jev scores changes in coupon issuance sizes (direction), bill share, guidance language ("at least the next
several quarters"), and buyback program changes. Long-only duration tilt among TLT, IEF, SHY and SPY for the quarter
after each announcement. Nested sets: trend / keywords / Jev. Leakage probe. DEV 2008–2017, TEST 2018+ (sealed).
Very few events, so keep the rule to one parameter and report power honestly.

## q10: j22_eia_steo (Jev)
EIA Short-Term Energy Outlook monthly text (eia.gov/outlooks/steo, archives 1990s+). Jev scores revisions to the oil
price forecast, supply and demand, inventories and natural-gas outlook vs the previous month. Long-only tilt among
XLE, USO, UNG, XOP and cash. Nested sets: momentum / keywords / Jev. Leakage probe. DEV 2008–2016, TEST 2017+ (sealed).

## q11: n01_pead_xbrl (no Jev)
Post-earnings-announcement drift with free XBRL data. From data/shared/companyfacts.zip (wait for
data/shared/companyfacts.READY), compute a standardized unexpected earnings measure: quarterly EPS (or net income per
share) vs the same quarter last year, scaled by the volatility of past surprises, dated by the 10-Q/10-K filing date. Also
compute the earnings-announcement return from prices. Long-only: top-quintile SUE among point-in-time S&P 500/400,
entered the day after filing and held 60 trading days. DEV 2012–19, TEST 2020+ (sealed). Costs 10–20bp, and 2×.

## q12: n02_profitability_trend (no Jev)
Gross profitability (Novy-Marx 2013) plus the trend switch. From companyfacts.zip: gross profit / total assets, as of
the latest filing before each rebalance. Long-only: top quintile of point-in-time S&P 500/400, rebalanced annually or
quarterly. Optional overlay: the SPY trend switch from strategies/deep_trend_switch/strategy.py (defense sleeve when
off). DEV 2012–19, TEST 2020+ (sealed). Costs 5–15bp, and 2×. Compare with the French profitability portfolio evidence in
research/ideas/FACTOR_EVIDENCE.md.

## q13: n03_net_issuance (no Jev)
Net share issuance (Pontiff & Woodgate 2008; Daniel & Titman 2006). From companyfacts.zip, compute the change in shares
outstanding over 12 months (split-adjusted; check the split handling carefully, since that is the main artifact).
Long-only: the firms with the largest share reductions, i.e. net buybacks, in point-in-time S&P 500/400, rebalanced
monthly or quarterly. DEV 2012–19, TEST 2020+ (sealed). Costs 5–15bp, and 2×.

## q14: n04_etf_seasonality (no Jev)
Cross-sectional return seasonality (Heston & Sadka 2008; Keloharju et al. 2016) in the 56-ETF universe. Rank ETFs by their
average return in the same calendar month over past years (lags of 12, 24, … up to 10 years) and hold the top 5 for that
month. Use the repo harness: DEV `etf_dev`, TEST `etf_holdout` (ALPHA_HOLDOUT=1, once, after PREREG.md). Also combine
it with the deep_trend_switch offense sleeve as a tie-breaker, and report the incremental value.

## q15: n05_calendar_overlays (no Jev)
Calendar overlays on `strategies/deep_trend_switch/strategy.py` using the repo harness:
- the pre-FOMC announcement drift (Lucca & Moench 2015): switch the defense sleeve into SPY for the 24h before scheduled
  FOMC announcements (Fed calendar from federalreserve.gov);
- the turn-of-the-month effect;
- pre-holiday effects.
Long-only, no leverage: an overlay can only move weight between sleeves. DEV `etf_dev`, TEST `etf_holdout` (once,
after PREREG.md). Report the incremental CAGR and whether each effect survived its publication date.
