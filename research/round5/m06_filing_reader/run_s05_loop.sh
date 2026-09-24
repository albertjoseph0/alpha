#!/bin/sh
# keep scoring new texts while the fetcher is still appending; final pass after it ends
cd /home/user/alpha/research/round5/m06_filing_reader
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
while pgrep -f "[s]05_score.py texts_all" >/dev/null; do sleep 30; done
while pgrep -f "[s]03_fetch_text" >/dev/null; do
  /home/user/alpha/.venv/bin/python s05_score.py texts_all.jsonl.gz sc 2>&1 | grep -E "^[0-9]|done"
  sleep 60
done
/home/user/alpha/.venv/bin/python s05_score.py texts_all.jsonl.gz sc 2>&1 | grep -E "^[0-9]|done"
echo LOOPDONE
