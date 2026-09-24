# Evidence check: long-only stock-factor portfolios (Ken French daily data, through 2026-07-31)

CAGR in %, value-weighted, before trading costs. Every portfolio below is long-only and could be
bought today with a stock basket or ETF. Jegadeesh & Titman published momentum in 1993 and Fama &
French published value in 1992–93, so 1994–2025 is the post-publication period.

| portfolio | 1927–63 | 1964–93 | 1994–2025 | 2008–25 | 2016–25 | max drawdown since 1927 |
|---|---:|---:|---:|---:|---:|---:|
| Market (buy & hold) | 9.3 | 10.6 | 10.9 | 11.4 | 15.0 | −84.1 |
| Top-decile momentum (12-2) | 13.7 | 19.4 | 14.7 | 13.0 | 18.2 | −84.3 |
| Large-cap winners (ME5 × PRIOR5) | 11.4 | 13.4 | 12.2 | 11.4 | 15.1 | −83.7 |
| Small value (ME1 × BM5) | 15.1 | 18.9 | 14.6 | 11.7 | 16.4 | −91.5 |
| Large value (ME5 × BM5) | 10.6 | 13.4 | 12.1 | 13.5 | 21.1 | −89.6 |
| Top-decile operating profitability | – | 10.6 (from 1963) | 13.1 | 14.0 | 17.9 | −54.6 (from 1963) |

Source files: 10_Portfolios_Prior_12_2_Daily, 25_Portfolios_ME_Prior_12_2_Daily, 25_Portfolios_5x5_Daily,
Portfolios_Formed_on_OP_Daily and F-F_Research_Data_Factors_daily.
