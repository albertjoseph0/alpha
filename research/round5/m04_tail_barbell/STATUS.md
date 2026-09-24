# m04 tail barbell: STATUS

## Done (previous instance, before the container restart)
- Data in data/round5/m04_tail_barbell/ (CBOE indices, yfinance SPY/SP500TR/IRX, 2026-09-22 SPX chain); `panel.pkl` built by prep_data.py.
- Pricer (pricing.py): linear-z skew rule ("linz", base) and SSVI (the more expensive sensitivity case). Validated on the real 2026-09-22 chain:
  linz/real mid is about 0.93-1.16 across put moneyness buckets; SSVI is 1.3-1.7x. See chain_check_linz.csv and chain_check.csv.

## Round 5b (this instance)
- [ ] run calibrate_surface.py -> data/.../surface.pkl (daily sa30, beta, sa by tenor)
- [ ] SSVI daily calibration for the expensive-pricing case
- [ ] backtest.py: daily mark-to-model, DEV grid (logged in grid_dev.csv)
- [ ] PREREG.md
- [ ] TEST run (once)
- [ ] CBOE benchmark cross-check (PPUT, VXTH, CLL)
- [ ] README.md with verdict

## Next step
Run calibrate_surface.py (about 15 min single-core).
