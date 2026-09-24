# Round 7 brief: 20 more agents (read fully, together with research/round5/BRIEF.md and research/round6/BRIEF_JEV.md)

About 35 research agents share this machine: 4 CPUs, 15 GB RAM, ~24 GB free disk, one IP for SEC EDGAR, and one Jev
account. The shared resources are the binding constraint, so be frugal:

* **CPU:** single-threaded only (`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`, no process pools). Run heavy scripts with
  `nice -n 10`, and keep any single job under ~20 min. Develop on small samples first.
* **RAM:** keep each process under ~700 MB. Use parquet and read only the columns you need.
* **Disk:** at most **600 MB** in your data folder. Extract what you need from raw downloads and delete the raw files.
* **SEC EDGAR:** use only `research/round5/sec.py` (`from sec import get`). It enforces one global request rate for
  all agents and caches responses. Expect it to be slow, so minimise requests:
  - Use EDGAR full-index/form.idx files, which list thousands of filings in one request.
  - Use the XBRL "frames" API (`https://data.sec.gov/api/xbrl/frames/us-gaap/<Concept>/USD/CY2019Q4I.json`), which
    returns one concept for all companies in one request.
  - Use the **bulk XBRL company-facts file** that the orchestrator is downloading once for everyone:
    `data/shared/companyfacts.zip` (about 1.4 GB). It is ready when `data/shared/companyfacts.READY` exists; poll
    with the Monitor tool or `sleep` in a loop, and don't download it yourself. Read the JSONs inside the zip
    without extracting it all (`zipfile`), and keep only the concepts and firms you need, as parquet in your own
    folder.
* **Jev:** your budget is in `research/round5/jev.py` (`BUDGET_USD`; round-7 agents get $1.50 each). Put
  many questions in one call per document. If `BudgetExceeded` is raised, stop scoring and work with what you
  have.
* **Point-in-time universes (read-only):**
  - S&P 500 intervals from 2019-10: `data/round5/m06_filing_reader/sp500_pit_intervals.csv`
  - S&P 400 monthly from 2012: `data/round5/m01_midcap_momentum/membership_monthly.csv`
  - m11 is rebuilding S&P 500 membership from 2011-12 under `data/round5/m11_tree_ranker/`; check its STATUS.md
  - m06's prices: `data/round5/m06_filing_reader/prices.parquet`
  - m01's prices: `close.pkl`
  Reuse these before downloading prices yourself.
* **ETF strategies:** use the repo harness (`harness/README.md`): `etf_dev` 2000–2015 for development and
  `etf_holdout` 2016+ as the sealed TEST (needs `ALPHA_HOLDOUT=1`; you may run it once, after PREREG.md).
* **STATUS.md** must be kept current. The session may end at any time, and a successor resumes from STATUS.md alone.
* **Do not git commit, and do not spawn subagents.** Your folder is `research/round7/<id>/`; your data folder is
  `data/round7/<id>/`.
* **Finish** with README.md: the report and verdict format from research/round5/BRIEF.md. For Jev agents, include
  the Jev-specific items from BRIEF_JEV.md (the three nested feature sets, the leakage probe, the frozen question
  list, and the cost used).
