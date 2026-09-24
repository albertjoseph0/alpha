# Round 5 brief: 10 moonshot agents (shared rules; read this fully first)

The user wants low-probability, high-payoff strategies: the target is **+20 percentage points of CAGR
per year over the relevant benchmark, after costs**. Most of these ideas are expected to fail. Your job
is to find out *honestly*, as quickly and cheaply as possible, whether yours is one that does not.
A clean "no, and here is why" is a successful result. A +20 backtest that is really an artifact is the
worst possible result.

## Background (read as needed; don't re-derive)
* `README.md` (harness overview), `harness/README.md` (engine rules), `research/deep/REPORT.md`
  (the one validated strategy so far: `strategies/deep_trend_switch/strategy.py`, a SPY trend switch
  between 12-1 ETF momentum and a Sharpe-momentum defensive sleeve, 12.3% vs 8.3% SPY over 2000-26).
* Text of the user's 4 source PDFs (Mandelbrot, Bouchaud, Wolfram) is in `research/extracted/*.txt`.
  Do not re-parse PDFs.
* Lessons from rounds 1-4: 1-day execution lag is essential (stale-price artifacts produced fake
  28% CAGRs); every free parameter tried is a hidden multiple test; most fancy signals collapse to
  momentum; trading costs and survivorship bias kill most edges.
* `research/ideas/FACTOR_EVIDENCE.md` has century-long French factor-portfolio CAGRs.
* Python: `.venv/bin/python` (pandas, numpy, torch 2.14 CPU, yfinance, etc.). Install extra packages
  with `uv pip install --python .venv/bin/python <pkg>` if needed.

## Hard rules (all agents)
1. **Tradeable today and allowed:** long-only or bounded downside (you can lose at most what you put
   in). No margin, no borrowed money, no short selling, no selling naked options, no perps/futures
   positions. Long options and prediction-market contracts are allowed (loss capped at premium).
   Crypto spot is allowed.
2. **No lookahead.** Every decision uses only information publicly available *before* the trade,
   including publication delays (filings: use the acceptance timestamp; trade at the next open or
   later). Minimum one bar/period between signal and execution.
3. **Costs.** Model realistic costs explicitly and state them (commissions, bid-ask spread, slippage,
   option spreads, exchange/taker fees). Also report results at 2x your cost assumption.
4. **Survivorship bias.** If your universe comes from today's lists (yfinance, current constituents,
   currently listed coins) you must quantify the bias (e.g. assume missing/delisted names return
   -100% or -50%, or use a point-in-time source). Say explicitly how you handled it.
5. **Pre-registration and the sealed test period.** Develop only on your dev period (given below). Before
   touching the test period, write `PREREG.md` in your folder: frozen rule, frozen parameters, costs,
   benchmark and the success criterion. Then run the test period **once** and report it as it
   comes out. Do not iterate after seeing it (if you must, report both and flag the second as tainted).
6. **Report:** CAGR after costs vs benchmark (dev and test, and at 2x costs), max drawdown, number of
   independent bets or trades, a capacity estimate (how many $ before the edge disappears), the main
   artifact you hunted for and what you found, and a verdict: `MOONSHOT CANDIDATE` (beats benchmark by
   >=20 pts/yr after costs in test), `REAL BUT SMALLER` (beats clearly but <20), or `NO EDGE`.
   Include what it would take to trade it live.

## Shared-machine etiquette (4 CPUs, 15 GB RAM, 28 GB disk shared by 10 agents, no GPU)
* Set `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`, use at most 1 CPU core, and no process pools. Keep single
  jobs under ~30 min; prefer smaller samples first.
* Keep RAM under ~1.5 GB per process.
* Keep disk under 2 GB: raw downloads go in `data/round5/<your_folder>/` (git-ignored). Aggregate
  early and delete raw files you no longer need.
* Network: SEC needs a User-Agent header, and must use exactly `alpha-research contact@alpha-research.dev`,
  at most 5 requests/s. Be polite to every API (sleep between calls, cache responses to disk).
* **Do not git commit or push.** The orchestrator commits everything. Only write inside
  `research/round5/<your_folder>/` and `data/round5/<your_folder>/`. Do not modify `harness/`,
  `strategies/`, or other agents' folders.
* Do not spawn subagents.

## Verified reachable from this container (2026-09-24)
Binance public archive `data.binance.vision` (spot & futures klines, aggTrades, fundingRate,
bookDepth; api.binance.com is blocked), CFTC, FINRA short volume, SqueezeMetrics DIX/GEX,
SEC EDGAR archives + full-text search (efts.sec.gov) + insider-transaction data sets
(`sec.gov/files/structureddata/data/insider-transactions-data-sets/YYYYqN_form345.zip`),
CBOE index histories (`cdn.cboe.com/api/global/us_indices/daily_prices/<VIX|SKEW|...>_History.csv`),
Kalshi API (`api.elections.kalshi.com/trade-api/v2`), Polymarket gamma and clob APIs, CoinGecko,
Hugging Face model downloads, PyPI, Ken French library, Wikipedia, iShares holdings CSVs, yfinance.
Blocked: api.binance.com, ICI, NYSE, paid order-book data. No ANTHROPIC_API_KEY is available.

## Round 5b (restart after the container reset): resilience rules
Round 5 agents were killed by a container restart before finishing. Round 5b runs 5 agents (m01, m02,
m05, m06 resumed and m11 new). Additional rules:
* **Resume, don't restart.** Read your folder's existing scripts and your data folder first. Reuse
  downloaded data; re-download only what is missing or corrupt.
* **Keep `STATUS.md` up to date** in your folder after every milestone (data done, dev result, prereg
  written, test run): what is done, key numbers so far, and the exact next step. If you are killed, a
  successor must be able to resume from STATUS.md alone.
* Save intermediate results to disk (csv or parquet) as soon as they are computed, never only in memory.
* **Data is read-only across agents.** You may read another agent's data folder, but never modify or
  delete files there. Don't overwrite or delete existing files in your own data folder that
  another agent may read (m01's membership and price files, m05's events, m06's S&P 500
  intervals and prices); add new files instead.
* With 5 agents on 4 CPUs, keep jobs single-threaded and short.

## Jev (TypeSafe) is available via Vercel AI Gateway (added 2026-09-24)
* Use the shared client `research/round5/jev.py` (`sys.path.insert(0, "research/round5"); from jev import ask`).
  Its docstring documents the question formats. The credential is injected by the proxy, so there is no key in code.
  Responses are cached on disk, and each agent has a hard USD cap (m05 $5, m06 $15, m11 $5; total
  account balance ~$55). At $0.042 per million input tokens, $1 buys about 24M tokens.
* Jev returns calibrated typed answers (yes/no probability, choice with probabilities, score). It is
  weak at arithmetic, counting and dates, so keep all numbers in code.
* **Lookahead rule for Jev:** ask only about facts stated in the text, never about the future. Strip
  company names, tickers and dates from the state. Jev's features feed a model you train on DEV
  only (boosted trees or logistic regression). Always compare against the same model without Jev
  features, and against a cheap dictionary baseline (Loughran–McDonald), on identical dates.
