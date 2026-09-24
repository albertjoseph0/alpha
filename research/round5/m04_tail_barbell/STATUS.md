# m04 tail barbell: STATUS (round 5b): COMPLETE

Verdict: **NO EDGE**. The full write-up is in README.md.

## Key numbers
- DEV 1990-2007: 0 of 24 configs beat SPY (-0.24 to -1.92 pts/yr). The frozen rule (30% OTM, 4-month, 1%/yr, 5x monetize) made 10.03% vs 10.27%.
- TEST 2008-2026, run once after PREREG.md: frozen rule 11.17% vs SPY 11.37% (-0.20 pts). 2x costs: -0.24. SSVI: -0.22.
  Canonical Universa-like config: -0.94 pts. 0 of 24 configs beat SPY on TEST.
- Post-test ladder/hold/20x grid (tainted): 0 of 48 beat SPY on DEV or TEST.
- Perfect-hindsight bound at a 3.3%/yr budget: +8 pts/yr on TEST at most, +5 on DEV.
- Real Cboe VXTH: 10.05% vs SP500TR 11.49% over 2008-26 (+114% in 2020). Without 2008 and 2020 it lags by 7.2 pts/yr.
- PPUT replication with the model: 7.21% vs 7.63% (1990-2026), yearly correlation 0.99.

## Done
All steps are done: calibration (raw and 21-day-mean SKEW, linz and SSVI), DEV grid, PREREG, one TEST run, post-test robustness grid,
oracle bound, PPUT/VXTH cross-check, README.

## Next
Nothing is required. Possible extension (not needed for the verdict): validate the 30%-OTM wing historically, if any
historical SPX chain snapshot (for example 2008 or 2020) becomes available.
