# Retention Model Update -- Findings & Cell Changes

All assumptions below (prices, mix, CAC, current curves) were read live from `model.xlsx` at run time -- nothing is hardcoded in this pipeline.

## Current plan mix (unaffected by this update)

- Monthly: 30%
- 3-Month: 65%
- 6-Month: 0%
- OTP: 5%

## Blended AOV impact

| Month | Old Blended AOV | New Blended AOV | Delta |
|---|---|---|---|
| 0 | £53.90 | £53.90 | £+0.00 |
| 3 | £35.94 | £36.66 | £+0.73 |
| 6 | £20.20 | £22.67 | £+2.46 |
| 9 | £13.03 | £14.69 | £+1.66 |
| 12 | £11.91 | £9.87 | £-2.04 |

## Closing Balance (Cash Flow!row169) -- NOT computed automatically

This pipeline can't recalculate the full workbook. Paste the values below into your live copy, let Excel recalculate, save as `model_after.xlsx` (keep the original as `model_before.xlsx`), then run:

```python
from business_impact import diff_closing_balance
diff_closing_balance('model_before.xlsx', 'model_after.xlsx')
```

## Confidence rating key

- **HIGH**: beats the current numbers on held-out data, wins consistently across CV folds, plenty of held-out points, no fit instability
- **MEDIUM**: beats the current numbers, but on a smaller sample or less consistently across folds
- **LOW**: either doesn't beat the current numbers, or the fit showed signs of instability (hit the optimizer's bounds) in at least one fold

## `Model Assumptions!C32`

- **Old value:** (read live from sheet -- see note)
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn: the live curve currently implies a 4.0%/month rate here (derived from the curve's own actual decay in this window, read directly from Cohort Modelling!row248 -- not from any single input cell, since input cells for this can be unused/inconsistent). Fitting sBG on 153 cohort-month data points (alpha=1.21, beta=2.88) gives 9.8%/month instead.
- **Confidence: HIGH** -- Improved on aggregate (0.0236 vs 0.0358), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £135.07 -> £129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)

## `Cohort Modelling!B20`

- **Old value:** 0.0400
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn (the cell the live curve actually uses): the live curve currently implies a 4.0%/month rate here (derived from the curve's own actual decay in this window, read directly from Cohort Modelling!row248 -- not from any single input cell, since input cells for this can be unused/inconsistent). Fitting sBG on 153 cohort-month data points (alpha=1.21, beta=2.88) gives 9.8%/month instead.
- **Confidence: HIGH** -- Improved on aggregate (0.0236 vs 0.0358), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £135.07 -> £129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)

## `Model Assumptions!C33`

- **Old value:** (read live from sheet -- see note)
- **New value:** 0.0575
- **Finding:** Monthly M13-24 churn: the live curve currently implies a 2.0%/month rate here (derived from the curve's own actual decay in this window, read directly from Cohort Modelling!row248 -- not from any single input cell, since input cells for this can be unused/inconsistent). Fitting sBG on 153 cohort-month data points (alpha=1.21, beta=2.88) gives 5.8%/month instead.
- **Confidence: HIGH** -- Improved on aggregate (0.0236 vs 0.0358), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £135.07 -> £129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)

## `Model Assumptions!C34`

- **Old value:** (read live from sheet -- see note)
- **New value:** 0.0315
- **Finding:** Monthly post-M24 churn: the live curve currently implies a 1.0%/month rate here (derived from the curve's own actual decay in this window, read directly from Cohort Modelling!row248 -- not from any single input cell, since input cells for this can be unused/inconsistent). Fitting sBG on 153 cohort-month data points (alpha=1.21, beta=2.88) gives 3.2%/month instead.
- **Confidence: HIGH** -- Improved on aggregate (0.0236 vs 0.0358), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £135.07 -> £129.46 (-4.2%, WORSENS); CAC:LTV: 3.463x -> 3.319x (WORSENS)

## `Cohort Modelling!K415 (I415, J415 flattened to =H415)`

- **Old value:** 0.1952 (via noisy compounded formula)
- **New value:** 0.236564
- **Finding:** Month-9 retention was computed by compounding noisy calendar-month ratios for months 7-8 (non-renewal months for a 3-month billing cycle). sBG (alpha=7.20, beta=10.73, fit on the quarterly-checkpoint cohort data) predicts month 9 directly without that contamination.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** 1st Yr LTV: £126.83 -> £129.93 (+2.4%, IMPROVES); CAC:LTV: 3.252x -> 3.332x (IMPROVES)

## `Model Assumptions!C43`

- **Old value:** (read live -- see note)
- **New value:** 0.1312
- **Finding:** 3-Month M7-12 churn (monthly-equiv.): derived from the same fit as month-9 above. sBG-implied monthly-equivalent rate for this window is 13.1%/month.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled. This specific tier is deeper into the curve than what the raw-curve CV above directly tested (42 held-out points total across the whole 3-Month curve) -- treat as less certain than the month-9 fix.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.

## `Model Assumptions!C44`

- **Old value:** (read live -- see note)
- **New value:** 0.1156
- **Finding:** 3-Month M13-24 churn (monthly-equiv.): derived from the same fit as month-9 above. sBG-implied monthly-equivalent rate for this window is 11.6%/month.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled. This specific tier is deeper into the curve than what the raw-curve CV above directly tested (42 held-out points total across the whole 3-Month curve) -- treat as less certain than the month-9 fix.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.

## `Model Assumptions!C45`

- **Old value:** (read live -- see note)
- **New value:** 0.0901
- **Finding:** 3-Month post-M24 churn (monthly-equiv.): derived from the same fit as month-9 above. sBG-implied monthly-equivalent rate for this window is 9.0%/month.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled. This specific tier is deeper into the curve than what the raw-curve CV above directly tested (42 held-out points total across the whole 3-Month curve) -- treat as less certain than the month-9 fix.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.

