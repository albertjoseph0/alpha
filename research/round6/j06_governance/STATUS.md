# j06 governance / pay-alignment index from DEF 14A (Jev): STATUS

Last updated: 2026-09-24 (start)

## Design (see PREREG.md once written)
- Season Y = proxies accepted in [1 Apr Y-1, 1 Jul Y) for S&P 500 PIT members at 30 Jun Y (m11, read-only);
  formation at the close of the first trading day of July Y; hold 12 months, equal weight, buy-and-hold.
- DEV seasons 2013-2019; TEST seasons 2020-2025 (sealed; run once).
- Feature sets: (a) size/value/momentum, (b) + keyword rules on the full proxy, (c) + Jev answers on a
  ~30k-char anonymized extract.

## Done
- s01_universe.py: DATA/universe.csv (6,495 firm-seasons after collapsing share classes), candidates.csv
  (DEF 14A + DEFC14A in window, latest first), manual CIK lineage fixes (OVR) after a name check.
  51 firm-seasons have no proxy (spin-offs, pending acquisitions, bank-regulator filers FRC/SBNY, BX/KKR).
- s02_fetch.py: fetch + HTML->text + annual-proxy check (CD&A + SCT). Pilot of 200 DEV proxies running.

## Next
- s03_select.py (topic-quota paragraph selection + anonymization), questions.py, pilot Jev on 200.
