# j10 merger arb — STATUS (update after every milestone)

Agent j10, Jev budget $1.50. Folder research/round7/j10_merger_arb/, data data/round7/j10_merger_arb/.
Run scripts from this folder with ../../../.venv/bin/python (nice -n 10, single thread).

## Pipeline
1. s01_index.py — form.idx 2011Q4..2026Q3 -> index_rows.parquet (SC TO-T, SC 14D9, PREM/DEFM14A/C, SC 13E3). DONE (11,090 rows)
2. s02_submissions.py — submissions JSON for 4,163 candidate target CIKs -> subs/part_*.parquet, meta_*.parquet
   (incremental; re-run resumes). RUNNING in background (log s02.log).

## Key decisions
- yfinance has NO delisted targets (tested 13 famous ones: 0 rows); stooq blocked; no free delisted source.
  Plan: entry price = post-announcement closing price disclosed in the target's DEFM14A ("latest practicable
  date") or the bidder's Offer to Purchase ("last full trading day before commencement"); entry = filing date + 1
  trading day at that (stale) price + drift penalty. Exit = final per-share cash paid (completion 8-K Item 2.01)
  on the completion date; broken deals exit at yfinance close after the termination 8-K, else unaffected price.

## Next step
Wait for s02; meanwhile write the parsers (8-K Item 1.01 text, entry price, completion consideration).
