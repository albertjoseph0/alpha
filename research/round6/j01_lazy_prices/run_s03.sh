#!/bin/bash
# sequential per-year chunks (each ~30 min); DEV years first, then TEST years
cd /home/user/alpha/research/round6/j01_lazy_prices
for y in 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026; do
  ../../../.venv/bin/python s03_sections.py $y-01-01 $y-12-31 >> ../../../data/round6/j01_lazy_prices/s03_$y.log 2>&1
done
echo ALLDONE >> ../../../data/round6/j01_lazy_prices/s03_2026.log
