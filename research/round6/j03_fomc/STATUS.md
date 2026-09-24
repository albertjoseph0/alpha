# j03_fomc STATUS

Idea: Jev reads FOMC statements (diff vs previous) and minutes; a tiny model tilts SPY/QQQ/IWM/TLT/IEF/SHY/GLD/cash.
DEV = meetings 1994-2012, TEST = 2013+ (sealed until PREREG.md exists).

## Done
- [ ] fetch Fed calendar, statements, minutes (fetch_fed.py -> data/round6/j03_fomc/)
- [ ] prices (fetch_prices.py)
- [ ] features a/b (features.py)
- [ ] Jev features (jev_features.py) + leakage probe (leak_probe.py)
- [ ] DEV walk-forward (dev.py)
- [ ] PREREG.md
- [ ] TEST run once (test.py)
- [ ] README.md

## Next step
Run fetch_fed.py.
