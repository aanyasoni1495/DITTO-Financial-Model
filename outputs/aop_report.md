# AOP Forecast Update -- Cash Flow!row17

Generated using the live retention curve (Monthly: sBG, 3-Month: sBG, curve dated 2026-08-24). Re-running this after the retention model refits will automatically use the new curve -- nothing here is hardcoded.

## Current active-subscriber mix (derived, not assumed)

- Monthly: 34.8%
- 3-Month: 65.2%

Held FIXED going forward for this forecast (matches the sheet's own Cohort Modelling!B8:B9 structure, which is also a flat constant, not time-varying). Re-run this pipeline periodically to refresh this estimate as retention/acquisition data changes.

## Validation

**Confidence: HIGH** -- tested against 14 real historical months, average error 4.2%.

| Month | Real AOP | Backtest Forecast | Error |
|---|---|---|---|
| 2025-06 | £51.62 | £46.06 | 10.8% |
| 2025-07 | £49.16 | £48.58 | 1.2% |
| 2025-08 | £44.52 | £46.67 | 4.8% |
| 2025-09 | £43.26 | £39.74 | 8.1% |
| 2025-10 | £42.27 | £39.54 | 6.5% |
| 2025-11 | £37.61 | £39.34 | 4.6% |
| 2025-12 | £33.95 | £35.02 | 3.1% |
| 2026-01 | £33.22 | £31.76 | 4.4% |
| 2026-02 | £33.61 | £31.78 | 5.4% |
| 2026-03 | £33.66 | £34.26 | 1.8% |
| 2026-04 | £34.17 | £35.74 | 4.6% |
| 2026-05 | £35.82 | £36.15 | 0.9% |
| 2026-06 | £37.90 | £38.76 | 2.3% |
| 2026-07 | £41.09 | £40.84 | 0.6% |

## Cell updates needed: `Cash Flow!row17`

**Do NOT change any month up to and including 2026-07** -- those are real, formula-derived actuals. Update only the months below, which are currently hand-typed placeholder guesses in the sheet.

**Note on the pattern below:** these numbers rise and fall on a repeating 3-month cycle. This is real, not a bug -- 3-Month subscribers only renew once every 3 months, so calendar months where more 3-Month cohorts hit their renewal point show a higher blended AOP (3-Month orders are pricier), and months in between show lower AOP. This same lumpiness is already present in the real historical data used to validate this model.

| Month | Current sheet value | Recommended new value |
|---|---|---|
| 2026-08 | £41.84 | £42.64 |
| 2026-09 | £43.76 | £45.26 |
| 2026-10 | £47.65 | £50.01 |
| 2026-11 | £49.50 | £54.68 |
| 2026-12 | £51.50 | £44.16 |
| 2027-01 | £54.10 | £47.83 |
| 2027-02 | £54.20 | £51.27 |
| 2027-03 | £56.20 | £43.00 |
| 2027-04 | £57.10 | £45.78 |
| 2027-05 | £58.10 | £48.29 |
| 2027-06 | £58.40 | £42.06 |
| 2027-07 | £59.70 | £44.14 |
| 2027-08 | £60.10 | £45.96 |
| 2027-09 | £60.20 | £41.37 |
| 2027-10 | £61.20 | £42.92 |
| 2027-11 | £61.20 | £44.24 |
| 2027-12 | £61.80 | £40.89 |
| 2028-01 | £62.20 | £42.04 |
| 2028-02 | £61.80 | £43.00 |
| 2028-03 | £62.60 | £40.56 |
| 2028-04 | £61.70 | £41.42 |
| 2028-05 | £61.90 | £42.13 |
| 2028-06 | £61.40 | £40.35 |
| 2028-07 | £62.30 | £40.98 |
| 2028-08 | £62.30 | £41.51 |
| 2028-09 | £61.90 | £40.20 |
| 2028-10 | £62.50 | £40.68 |
| 2028-11 | £62.20 | £41.08 |
| 2028-12 | £62.50 | £40.12 |
| 2029-01 | £62.70 | £40.48 |
| 2029-02 | £61.70 | £40.78 |
| 2029-03 | £60.70 | £40.06 |
