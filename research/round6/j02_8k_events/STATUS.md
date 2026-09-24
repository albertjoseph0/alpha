# j02 8-K material events: STATUS (updated 02:42 UTC)

## Done
- s01_list_8k.py -> DATA/events_8k.csv: 27,118 non-earnings 8-Ks (form 8-K, no Item 2.02, >=1 of items 1.01 1.02 2.01 2.05
  2.06 3.01 4.01 4.02 5.02 7.01 8.01), S&P 500 point-in-time members (m06 intervals), 2019-10..2026-09. DEV 13,322; TEST 13,796.
  S&P 400 dropped: the $5 Jev budget cannot cover a second ~25k-filing universe (and m01 has no opens / CIK map for removed names).
- s03_returns.py -> DATA/event_returns.parquet: entry at first open after acceptance (<09:15 ET -> same-day open), open-to-open
  returns for H=5,10,20,40,60 and SPY; pre-event price features. 1,172 events (4.3%) lack prices (delisted names: DFS, WBA, PXD, SIVB...).
- DEV event study by item (all tiny): mean AR20 +0.10% (t 0.9), AR60 +0.38% (t 1.4).
- Code: state.py (anonymised Jev state), j02_questions.py (Q_V1 frozen + Q_LEAK), s05_textfeat.py (LM + keywords),
  s06_panel.py, s07_dev.py (rules + walk-forward HGB for sets A/B/C, 4 half-year folds 2021-2022), bt.py (K-slot portfolio sim).
- s07_dev.py base (sets A, B on partial text) ran: IC 0.02-0.04, portfolio excess vs SPY -6..+1.4 pts/yr in 2021-22.

## Running (all resumable by rerunning the same command)
- s02_fetch_text.py 2019-10-01 2021-06-30 texts.jsonl.gz  (log s02_dev1.log)
- s02_fetch_text.py 2021-07-01 2022-12-31 texts_dev2.jsonl.gz (log s02_dev2.log)
- s02_fetch_text.py 2023-01-01 2026-12-31 texts_test.jsonl.gz (log s02_test.log); TEST texts are data only, not evaluated.
- Jev spend so far ~$0.03 (324 DEV docs with Q_V1; ~2.1k tokens/doc -> ~$2.5 for all 27k docs).

## Next
- When DEV texts finish: s05_textfeat.py; s04_jev.py 2019-10-01 2022-12-31 v1; leakage probe (s08_leak.py); s07_dev.py v1.
- Then PREREG.md, Jev on TEST (s04_jev.py 2023-01-01 2026-12-31 v1), s09_test.py once, README.md.
