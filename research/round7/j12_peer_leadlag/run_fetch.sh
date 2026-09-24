#!/bin/sh
# Background fetch loop: submissions (s02) then 10-K Item 1 docs (s03), DEV formations first, then TEST formations.
# Each python run is time-boxed (<20 min); the loop restarts it until the done-marker exists.
cd /home/user/alpha/research/round7/j12_peer_leadlag
D=/home/user/alpha/data/round7/j12_peer_leadlag
PY=/home/user/alpha/.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
i=0
while [ ! -f $D/s02_done ] && [ $i -lt 10 ]; do
  nice -n 10 $PY s02_submissions.py >> $D/s02.log 2>&1
  i=$((i+1))
done
for Y in 2012,2015,2018 2021,2024; do
  M=$D/s03_done_$(echo $Y | tr ',' '_')
  i=0
  while [ ! -f $M ] && [ $i -lt 40 ]; do
    nice -n 10 $PY s03_docs.py $Y 18 >> $D/s03.log 2>&1
    i=$((i+1))
  done
done
echo "fetch loop finished" >> $D/s03.log
