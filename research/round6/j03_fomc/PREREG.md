# j03_fomc pre-registration (written before any TEST backtest)

Written 2026-09-24, after DEV (events 1994-2012) and before any TEST (2013-01-01 onward) backtest.
Jev features for TEST documents were computed with the frozen question set v1, but no TEST returns
have been looked at.

## Frozen rule
* **Events:** every FOMC statement and every set of minutes. The event day is the release day,
  or the next trading day if it falls on a non-trading day.
* **Features:** `lib.FEATS`, three nested sets on identical events.
  * (a) `a_notext`: the event-day 2y yield change, SPY return and TLT return.
  * (b) `b_dict`: (a) plus a hawk/dove phrase dictionary (net and change), cosine similarity to the
    previous document of the same kind, and the number of dissents.
  * (c) `c_jev`: (b) plus Jev question set v1 (`jev_features.py`, unchanged): J_hawk, J_guid, J_infl,
    J_bs and J_risk.
* **Model:** two ridge regressions, with the penalty equal to 1.0 × n_train on features standardised
  within document kind. One targets the next-period SPY excess return over cash, the other the TLT
  excess return; each period runs from the event close to the next event close. Coefficients and
  standardisation are **frozen on all DEV events (1994-2012)**. The predictions are z-scored with
  the moments of the DEV in-sample fit.
* **Allocation (long-only, no leverage):**
  * Equity weight = clip(0.6 + 0.4·z_eq, 0, 1), split 50/25/25 across SPY/QQQ/IWM.
  * 20% of the remainder goes to GLD.
  * The rest goes to TLT if z_dur > 0.5, SHY if z_dur < −0.5, and IEF otherwise.
* **Execution (PRIMARY):** at the **next trading day's open** after the event (1-bar lag). The
  event-day close execution is also reported, but it is not tradeable, because the features use
  that same close.
* **Costs:** 3 bp per side on traded notional (ETF spread plus slippage, no commission). Results
  are also reported at 6 bp (2×).

## Primary hypothesis and success criteria (TEST: 2013-01-01 → latest price)
1. **Jev works** only if `c_jev` beats `b_dict` in TEST. Both use the frozen coefficients and
   next-open execution at 3 bp. The test statistic is the paired event-period log-return
   difference; "clearly" means t > 2. The OOS IC of c must also be higher than b's.
2. **Verdict vs SPY (brief):**
   * `MOONSHOT CANDIDATE`: c_jev's CAGR beats SPY by ≥ 20 pts/yr after costs.
   * `REAL BUT SMALLER`: c_jev beats SPY and 60/40 clearly (paired t > 2), by less than 20 pts/yr.
   * `NO EDGE`: anything else.
3. **Secondary (reported, not used for the verdict):**
   * The expanding-window refit variant.
   * The a/b sets, the neutral allocator (z = 0), and 60/40 SPY/IEF.

## Prior from DEV (for the record)
* Walk-forward OOS 2000-2012, 216 events.
  * OOS IC for the equity target: a +0.087, b +0.012, c −0.076.
  * SE(IC) is about 0.068, so none of these is significant.
* Paired c − b is −4.1 pts/yr (t = −2.29).
* So the expected result is **NO EDGE**, and Jev is expected to add nothing.
* The TEST run is still done once, as registered, to measure it out of sample.

## Power
* TEST has about 224 events, so SE(IC) is about 0.067.
* Only an IC of about 0.13 or more is detectable at 2σ.
* An incremental Jev IC of 0.05 over b would need roughly 1,600 events, which is about 60 years of
  FOMC documents.
* The design can only detect a large effect.
