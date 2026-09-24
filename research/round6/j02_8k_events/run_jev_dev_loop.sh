#!/bin/sh
# Score DEV texts with Jev as they arrive; stop once the fetcher has moved past DEV (a 2023+ date in s02x.log).
L=/home/user/alpha/data/round6/j02_8k_events
while true; do
  ../../../.venv/bin/python s04_jev.py 2019-10-01 2022-12-31 v1 >> $L/s04_v1_dev.log 2>&1
  if grep -qE " 202[3-6]-" $L/s02x.log || grep -q "^done" $L/s02x.log; then
    ../../../.venv/bin/python s04_jev.py 2019-10-01 2022-12-31 v1 >> $L/s04_v1_dev.log 2>&1
    echo ALLDONE >> $L/s04_v1_dev.log; break
  fi
  sleep 240
done
