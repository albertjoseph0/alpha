# m04 tail barbell: STATUS (round 5b)

## Done
- Previous instance: data in data/round5/m04_tail_barbell/, panel.pkl (prep_data.py), pricer (pricing.py) validated on
  the 2026-09-22 SPX chain (linz/real mid 0.93-1.16, SSVI 1.3-1.7x).
- surface.pkl: daily linz calibration to raw VIX/SKEW (calibrate_surface.py; 700 of 9244 days with residual 1e-3 to 0.06, harmless).
- surface_ssvi.pkl: daily SSVI calibration to raw SKEW (calibrate_ssvi.py).
- FINDING: the raw daily SKEW is noisy. In flat markets (July 1990, Nov 2006) SKEW moves 105->132 and the 30%-OTM
  model mark jumps 10-100x. That would create fake "crash gains" and fake monetisations. Base surface is therefore
  calibrated to the trailing 21-day mean SKEW (surface_s21.pkl, surface_ssvi_s21.pkl; queue script running).
  The raw-SKEW surface is kept as the "rawskew" sensitivity.
- pput_check.py: replicating CBOE PPUT (5% OTM 1-month puts) with the raw linz surface gives CAGR 7.23% vs real 7.63%
  (1990-2026), yearly corr 0.991, mean yearly diff -0.36 pts (1990s: -0.06; 2000-07: -1.2; 2008+: -0.15).
- backtest.py engine done; smoke test DEV (raw surface, 30% OTM, 2m, 3.3%/yr): CAGR 8.9% vs SPY 10.3%.

## Next
1. Wait for surface_s21.pkl and surface_ssvi_s21.pkl (logs calibrate_*_s21.log), then run grid_dev.py -> grid_dev.csv.
2. Write PREREG.md with the selected config, then evaluate.py test (once).
3. Rerun pput_check.py on the s21 surface, run the VXTH cross-check, write README.md.
