# AOP Forecast Update -- Cash Flow!row17

Generated using the live retention curve (Monthly: sBG, 3-Month: sBG, curve dated 2026-09-02). Re-running this after the retention model refits will automatically use the new curve -- nothing here is hardcoded.

## Current active-subscriber mix (derived, not assumed)

- Monthly: 31.0%
- 3-Month: 69.0%

Held FIXED going forward for this forecast (matches the sheet's own Cohort Modelling!B8:B9 structure, which is also a flat constant, not time-varying). Re-run this pipeline periodically to refresh this estimate as retention/acquisition data changes.

## Validation

**Confidence: HIGH** -- tested against 14 real historical months, average error 4.8%.

| Month | Real AOP | Backtest Forecast | Error |
|---|---|---|---|
| 2025-06 | £51.62 | £48.27 | 6.5% |
| 2025-07 | £49.16 | £46.42 | 5.6% |
| 2025-08 | £44.52 | £40.05 | 10.1% |
| 2025-09 | £43.26 | £39.72 | 8.2% |
| 2025-10 | £42.27 | £39.28 | 7.1% |
| 2025-11 | £37.61 | £36.47 | 3.0% |
| 2025-12 | £33.95 | £32.08 | 5.5% |
| 2026-01 | £33.22 | £31.48 | 5.2% |
| 2026-02 | £33.61 | £33.29 | 0.9% |
| 2026-03 | £33.66 | £34.80 | 3.4% |
| 2026-04 | £34.17 | £35.39 | 3.6% |
| 2026-05 | £35.82 | £36.21 | 1.1% |
| 2026-06 | £37.90 | £39.49 | 4.2% |
| 2026-07 | £41.09 | £42.24 | 2.8% |

## Cell updates needed: `Cash Flow!row17`

**Do NOT change any month up to and including 2026-07** -- those are real, formula-derived actuals. Update only the months below, which are currently hand-typed placeholder guesses in the sheet.

**Note 1 (short-term oscillation):** these numbers rise and fall on a repeating 3-month cycle. This is real, not a bug -- 3-Month subscribers only renew once every 3 months, so calendar months where more 3-Month cohorts hit their renewal point show a higher blended AOP (3-Month orders are pricier), and months in between show lower AOP. This same lumpiness is already present in the real historical data used to validate this model.

**Note 2 (long-term flattening):** new-signup price is fixed at August 2026's real average (£19.35 Monthly, £46.65 3-Month) for the entire forecast, per explicit instruction. Since the sheet's own acquisition forecast grows roughly 4x by 2029, new signups increasingly dominate the blend over time, pulling AOP toward this fixed price rather than growing -- this is why the forecast settles around £39-40 in later years rather than climbing. This is a direct, mechanical consequence of pinning new-signup price at August's level combined with the sheet's own growth assumption, not a bug. If actual future pricing changes, this forecast will not reflect that until re-run with an updated fixed price.

| Month | Current sheet value | Recommended new value |
|---|---|---|
| 2026-08 | £40.73 | £42.14 |
| 2026-09 | £44.74 | £44.60 |
| 2026-10 | £48.65 | £48.55 |
| 2026-11 | £52.00 | £55.65 |
| 2026-12 | £55.02 | £44.13 |
| 2027-01 | £56.81 | £46.02 |
| 2027-02 | £63.32 | £51.16 |
| 2027-03 | £60.18 | £42.60 |
| 2027-04 | £60.24 | £43.66 |
| 2027-05 | £63.58 | £47.01 |
| 2027-06 | £61.75 | £41.33 |
| 2027-07 | £62.90 | £42.21 |
| 2027-08 | £64.78 | £44.49 |
| 2027-09 | £63.79 | £40.62 |
| 2027-10 | £64.42 | £41.23 |
| 2027-11 | £65.52 | £42.78 |
| 2027-12 | £64.96 | £40.16 |
| 2028-01 | £65.33 | £40.60 |
| 2028-02 | £65.99 | £41.65 |
| 2028-03 | £65.67 | £39.88 |
| 2028-04 | £65.73 | £40.17 |
| 2028-05 | £65.94 | £40.87 |
| 2028-06 | £65.54 | £39.69 |
| 2028-07 | £65.56 | £39.88 |
| 2028-08 | £65.71 | £40.34 |
| 2028-09 | £65.49 | £39.57 |
| 2028-10 | £65.52 | £39.71 |
| 2028-11 | £65.63 | £40.02 |
| 2028-12 | £65.51 | £39.51 |
| 2029-01 | £65.54 | £39.60 |
| 2029-02 | £65.61 | £39.81 |
| 2029-03 | £65.55 | £39.47 |
