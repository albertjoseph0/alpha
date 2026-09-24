#!/bin/sh
cd /home/user/alpha/research/round5/m06_filing_reader
export OMP_NUM_THREADS=1
while pgrep -f "[s]07_jev.py" >/dev/null; do sleep 30; done
while pgrep -f "[s]03_fetch_text" >/dev/null; do
  /home/user/alpha/.venv/bin/python -u s07_jev.py 2>&1 | grep -v "^error"
  sleep 60
done
/home/user/alpha/.venv/bin/python -u s07_jev.py 2>&1 | grep -v "^error"
/home/user/alpha/.venv/bin/python -u s07_jev.py 2>&1 | tail -3   # fill any failed calls
echo LOOPDONE
