# Round 1 review (development-period evidence only)

The seven round-1 agents each submitted one final strategy. All numbers below are CAGR
from the harness. The 2000–2026 holdout has **not** been run yet; it is reserved for the
end so that round-2 design isn't influenced by it.

| strategy | dir | dev 1950–99 | dev_a 1950–74 | dev_b 1975–99 | early 1932–49 |
|---|---|---:|---:|---:|---:|
| fractal:mfspec_ruler_rotation | mf_spectrum | **16.43%** | 12.98% | 19.81% | 11.99% |
| fractal:hurst_xs_persistence | hurst_regime | 16.17% | 12.95% | 19.48% | 11.19% |
| fractal:tails_chiseled_frontier | tail_risk | 15.64% | 11.97% | 19.24% | 10.71% |
| fractal:mfvol_ttmom_kelly | multifractal_vol | 15.51% | 12.55% | 18.43% | 6.92% |
| transformer:alloc_axial_ens4_noweeksign | transformer_allocator | 14.74% | 10.40% | 18.94% | — |
| transformer:gpt_token_kelly | token_gpt | 14.11% | 13.11% | 14.50% | — |
| hybrid:fractal_transformer_kelly | fractal_transformer | 13.39% | 9.34% | 17.36% | — |
| benchmark: buy & hold market | | 13.40% | 9.42% | 17.53% | 10.52% |
| benchmark: equal-weight 12 industries | | 13.54% | 9.91% | 17.13% | 11.58% |

## Findings

1. **One idea did all the work: cross-sectional industry momentum.** Five of seven agents
   independently converged on 12-month industry relative strength. Their daily returns
   correlate 0.96–0.98 with each other, and their *excess* returns over buy & hold
   correlate 0.7–0.8. They are the same bet.
2. **The fractal signals added little beyond it.** Specifically:
   * Hurst, λ², spectrum width, Hölder exponents and tail indices carried no information
     beyond plain realized volatility.
   * The one useful fractal idea was *path smoothness*: Mandelbrot's ruler / fractal
     dimension, which ranks trends by efficiency.
   * Splitting 12-month moves into jump days and regular days: the jump part has zero
     cross-sectional information, and the smooth part carries all of it. This is the Noah
     vs Joseph effect.
3. **Market timing always cost CAGR.** Every attempt lost to buy & hold in dev or in 1932–49:
   vol-targeting, Kelly caps, tail / shock filters, turbulence switches, Hurst gates.
   Without leverage, de-risking can only reduce exposure. Turbulent states were
   followed by the *best* returns (Mandelbrot heresy 3).
4. **Transformers:**
   * The token GPT barely beat the unigram baseline, so direction is nearly unpredictable.
   * The end-to-end allocator learned a *few-week* industry-selection signal (+1.3 points over
     equal weight), a different horizon from the 12-month effect.
   * Synthetic multifractal pretraining improved *volatility* forecasts, but not CAGR.
5. **Where momentum loses: sharp rebound years.** The worst years relative to buy & hold were
   1975 (B&H +38%), 1950, 1955, 1954 and 1996, when prior losers rallied. It wins in down
   years (1973, 1957). Drawdowns are market-like (−42% to −46%).
6. **Breadth is the lever (orchestrator check, `research/round1/breadth_check.py`).** Plain
   12-1 momentum, top third, equal weight:

   | universe | dev | dev_a | dev_b | early 1932–49 |
   |---|---:|---:|---:|---:|
   | 12 industries | 16.06% | 12.82% | 19.21% | 11.30% |
   | **49 industries** | **17.58%** | **15.08%** | **19.98%** | **15.97%** |

   With 12 industries the edge disappears in 1932–49, and concentration hurts there (top
   tenth: 7.99%). With 49 it beats buy & hold in every period. This fits the fundamental
   law of active management: skill × √breadth.

## Decision for round 2 (power-law allocation)
Concentrate essentially all effort on the one thing that works: **cross-sectional momentum on
the 49-industry universe**, attacked from several distinct angles (see `research/PLAN.md`).
