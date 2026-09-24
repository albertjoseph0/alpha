#!/bin/bash
# incremental: extract -> prices -> edgar status, repeated while the fetch runs
PY=/home/user/alpha/.venv/bin/python
cd /home/user/alpha/research/round6/j05_ipo_quality
while true; do
  $PY s04_extract.py > /dev/null 2>&1
  $PY s05_prices.py > /dev/null 2>&1
  $PY s06_edgar_status.py > /dev/null 2>&1
  echo "$(date +%T) pass done $(wc -l < /home/user/alpha/data/round6/j05_ipo_quality/price_map.csv)"
  pgrep -f s03_fetch.py > /dev/null || break
  sleep 300
done
$PY s04_extract.py; $PY s05_prices.py; $PY s06_edgar_status.py
echo FINAL
