# j04 spin-offs STATUS
- [x] Read briefs; folders created.
- [~] Step 1 `01_fetch_docs.py`: picks latest information statement per CIK (m08 EFTS hits with when-issued/regular-way), fetches via sec.get, stores text in data/round6/j04_spinoffs/text/. (running; rerun is resumable)
- [ ] Step 2 `02_extract.py`: regex metadata (ticker, exchange, ratio, parent) + anonymised section windows -> meta.csv, sections/
- [ ] Step 3 `03_prices.py`: EDGAR submissions + yfinance -> events.csv, prices/
- [ ] Step 4 Jev features (questions.py v1 frozen; tested on 1 doc: Lands End answers correct, ~8.7k tokens/doc)
- [ ] Step 5 keyword baseline, DEV backtest, leakage probe
- [ ] PREREG.md, TEST once, README.md
Jev spend so far: ~$0.0004.
Next step: wait for 01 to finish (docs.csv written at end), then run 02, 03.
