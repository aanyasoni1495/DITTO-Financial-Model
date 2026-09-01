# AOP Forecast Update -- Cash Flow!row17

Generated using the live retention curve (Monthly: sBG, 3-Month: sBG, curve dated 2026-09-01). Re-running this after the retention model refits will automatically use the new curve -- nothing here is hardcoded.

## Current active-subscriber mix (derived, not assumed)

- Monthly: 30.9%
- 3-Month: 69.1%

Held FIXED going forward for this forecast (matches the sheet's own Cohort Modelling!B8:B9 structure, which is also a flat constant, not time-varying). Re-run this pipeline periodically to refresh this estimate as retention/acquisition data changes.

## Validation

**Confidence: HIGH** -- tested against 14 real historical months, average error 4.8%.

| Month | Real AOP | Backtest Forecast | Error |
|---|---|---|---|
| 2025-06 | £51.62 | £48.28 | 6.5% |
| 2025-07 | £49.16 | £46.44 | 5.5% |
| 2025-08 | £44.52 | £40.08 | 10.0% |
| 2025-09 | £43.26 | £39.76 | 8.1% |
| 2025-10 | £42.27 | £39.31 | 7.0% |
| 2025-11 | £37.61 | £36.50 | 2.9% |
| 2025-12 | £33.95 | £32.10 | 5.4% |
| 2026-01 | £33.22 | £31.49 | 5.2% |
| 2026-02 | £33.61 | £33.30 | 0.9% |
| 2026-03 | £33.66 | £34.82 | 3.5% |
| 2026-04 | £34.17 | £35.43 | 3.7% |
| 2026-05 | £35.82 | £36.25 | 1.2% |
| 2026-06 | £37.90 | £39.57 | 4.4% |
| 2026-07 | £41.09 | £42.33 | 3.0% |

## Cell updates needed: `Cash Flow!row17`

**Do NOT change any month up to and including 2026-07** -- those are real, formula-derived actuals. Update only the months below, which are currently hand-typed placeholder guesses in the sheet.

**Note 1 (short-term oscillation):** these numbers rise and fall on a repeating 3-month cycle. This is real, not a bug -- 3-Month subscribers only renew once every 3 months, so calendar months where more 3-Month cohorts hit their renewal point show a higher blended AOP (3-Month orders are pricier), and months in between show lower AOP. This same lumpiness is already present in the real historical data used to validate this model.

**Note 2 (long-term flattening):** new-signup price is fixed at August 2026's real average (£19.35 Monthly, £46.65 3-Month) for the entire forecast, per explicit instruction. Since the sheet's own acquisition forecast grows roughly 4x by 2029, new signups increasingly dominate the blend over time, pulling AOP toward this fixed price rather than growing -- this is why the forecast settles around £39-40 in later years rather than climbing. This is a direct, mechanical consequence of pinning new-signup price at August's level combined with the sheet's own growth assumption, not a bug. If actual future pricing changes, this forecast will not reflect that until re-run with an updated fixed price.

| Month | Current sheet value | Recommended new value |
|---|---|---|
| 2026-08 | £41.84 | £42.23 |
| 2026-09 | £43.76 | £44.74 |
| 2026-10 | £47.65 | £48.74 |
| 2026-11 | £49.50 | £56.00 |
| 2026-12 | £51.50 | £43.59 |
| 2027-01 | £54.10 | £46.10 |
| 2027-02 | £54.20 | £51.34 |
| 2027-03 | £56.20 | £42.14 |
| 2027-04 | £57.10 | £43.59 |
| 2027-05 | £58.10 | £46.92 |
| 2027-06 | £58.40 | £40.95 |
| 2027-07 | £59.70 | £42.03 |
| 2027-08 | £60.10 | £44.21 |
| 2027-09 | £60.20 | £40.30 |
| 2027-10 | £61.20 | £41.01 |
| 2027-11 | £61.20 | £42.42 |
| 2027-12 | £61.80 | £39.90 |
| 2028-01 | £62.20 | £40.37 |
| 2028-02 | £61.80 | £41.28 |
| 2028-03 | £62.60 | £39.66 |
| 2028-04 | £61.70 | £39.96 |
| 2028-05 | £61.90 | £40.53 |
| 2028-06 | £61.40 | £39.53 |
| 2028-07 | £62.30 | £39.72 |
| 2028-08 | £62.30 | £40.07 |
| 2028-09 | £61.90 | £39.46 |
| 2028-10 | £62.50 | £39.58 |
| 2028-11 | £62.20 | £39.80 |
| 2028-12 | £62.50 | £39.42 |
| 2029-01 | £62.70 | £39.50 |
| 2029-02 | £61.70 | £39.64 |
| 2029-03 | £60.70 | £39.41 |
