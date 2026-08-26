# Retention Model Update -- Findings & Cell Changes

## Current plan mix (unaffected by this update)

- Monthly: 30%
- 3-Month: 65%
- 6-Month: 0%
- OTP: 5%

Retention changes affect each plan's LTV, not this mix. If you change the mix itself, that's a separate input (`Cohort Modelling!B8:B11`) and would need re-running the business-impact numbers below.

## Blended AOV impact (Cohort Modelling!row249 + row417, weighted by mix above)

Uses the net-price 3-Month path (`B418`=£81), not the list-price path (`B6`=£100) -- see the note in `business_impact.py` about why these two disagree in the sheet already.

| Month | Old Blended AOV | New Blended AOV | Delta |
|---|---|---|---|
| 0 | £53.90 | £53.90 | £+0.00 |
| 3 | £35.94 | £36.66 | £+0.73 |
| 6 | £20.20 | £22.67 | £+2.46 |
| 9 | £13.03 | £14.69 | £+1.66 |
| 12 | £11.91 | £9.87 | £-2.04 |

## Closing Balance (Cash Flow!row169) -- NOT computed automatically

This pipeline can't recalculate the full workbook (the appendix sheets alone are too large for a reliable automated recalc). To get this number: paste the values below into your live copy, let Excel recalculate, save it, then run:

```python
from business_impact import diff_closing_balance
diff_closing_balance('model_before.xlsx', 'model_after.xlsx')
```

## `Model Assumptions!C32`

- **Old value:** 0.0400
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn: sheet assumed a flat 4.0%/month churn rate here. Fitting a shifted-Beta-Geometric model on 153 cohort-month data points (alpha=1.21, beta=2.88) and backing out the equivalent flat rate for this window gives 9.8%/month instead.
- **Why changed (validation):** Cross-validated with time-series CV (5 folds, 125 held-out points): new rate MAE=0.0236 vs old rate MAE=0.0358 (improvement).
- **Business impact:** 1st Yr LTV: 135.07 -> 129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)
- **Confidence:** HIGH

## `Cohort Modelling!B20`

- **Old value:** 0.0400
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn (orphaned duplicate): sheet assumed a flat 4.0%/month churn rate here. Fitting a shifted-Beta-Geometric model on 153 cohort-month data points (alpha=1.21, beta=2.88) and backing out the equivalent flat rate for this window gives 9.8%/month instead.
- **Why changed (validation):** Cross-validated with time-series CV (5 folds, 125 held-out points): new rate MAE=0.0236 vs old rate MAE=0.0358 (improvement).
- **Business impact:** 1st Yr LTV: 135.07 -> 129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)
- **Confidence:** HIGH

## `Model Assumptions!C33`

- **Old value:** 0.0200
- **New value:** 0.0575
- **Finding:** Monthly M13-24 churn: sheet assumed a flat 2.0%/month churn rate here. Fitting a shifted-Beta-Geometric model on 153 cohort-month data points (alpha=1.21, beta=2.88) and backing out the equivalent flat rate for this window gives 5.8%/month instead.
- **Why changed (validation):** Cross-validated with time-series CV (5 folds, 125 held-out points): new rate MAE=0.0236 vs old rate MAE=0.0358 (improvement).
- **Business impact:** 1st Yr LTV: 135.07 -> 129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)
- **Confidence:** HIGH

## `Model Assumptions!C34`

- **Old value:** 0.0100
- **New value:** 0.0315
- **Finding:** Monthly post-M24 churn: sheet assumed a flat 1.0%/month churn rate here. Fitting a shifted-Beta-Geometric model on 153 cohort-month data points (alpha=1.21, beta=2.88) and backing out the equivalent flat rate for this window gives 3.2%/month instead.
- **Why changed (validation):** Cross-validated with time-series CV (5 folds, 125 held-out points): new rate MAE=0.0236 vs old rate MAE=0.0358 (improvement).
- **Business impact:** 1st Yr LTV: 135.07 -> 129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)
- **Confidence:** HIGH

## `Cohort Modelling!K415 (I415, J415 flattened to =H415)`

- **Old value:** 0.1952 (via noisy compounded formula)
- **New value:** 0.236569
- **Finding:** Month-9 retention was computed by compounding two noisy calendar-month ratios (month 7->8->9), even though months 7-8 aren't real renewal points for a 3-month billing cycle -- see prior conversation for the exact -72%/+189% swing that was being multiplied through. sBG (fit on cohort-level quarterly checkpoints, alpha=7.20, beta=10.72) predicts month 9 directly without that contamination.
- **Why changed (validation):** Structural fix (formula -> static value), not a tier-fit -- see raw-curve CV above (4 folds, 42 held-out points, MAE 0.0528 vs sheet 0.0845).
- **Business impact:** 1st Yr LTV: 126.83 -> 129.93 (+2.4%, IMPROVES); CAC:LTV: 3.252x -> 3.332x (IMPROVES)
- **Confidence:** MEDIUM (isolated structural fix, less exposed to small-sample tier-fit noise)

## `Model Assumptions!C43`

- **Old value:** 0.0300
- **New value:** 0.1312
- **Finding:** 3-Month M7-12 churn (monthly-equiv.): sheet assumed 3.0%/month. sBG-implied monthly-equivalent rate for this window is 13.1%/month.
- **Why changed (validation):** Based on the same fit as month-9 above. Only 42 held-out data points exist this deep in the curve -- treat as directionally useful, not fully validated.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.
- **Confidence:** MEDIUM

## `Model Assumptions!C44`

- **Old value:** 0.0200
- **New value:** 0.1156
- **Finding:** 3-Month M13-24 churn (monthly-equiv.): sheet assumed 2.0%/month. sBG-implied monthly-equivalent rate for this window is 11.6%/month.
- **Why changed (validation):** Based on the same fit as month-9 above. Only 42 held-out data points exist this deep in the curve -- treat as directionally useful, not fully validated.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.
- **Confidence:** MEDIUM

## `Model Assumptions!C45`

- **Old value:** 0.0100
- **New value:** 0.0900
- **Finding:** 3-Month post-M24 churn (monthly-equiv.): sheet assumed 1.0%/month. sBG-implied monthly-equivalent rate for this window is 9.0%/month.
- **Why changed (validation):** Based on the same fit as month-9 above. Only 42 held-out data points exist this deep in the curve -- treat as directionally useful, not fully validated.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.
- **Confidence:** MEDIUM

