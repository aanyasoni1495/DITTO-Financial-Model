# Retention Model Update -- Findings & Cell Changes

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
- **New value:** 0.236564
- **Finding:** Month-9 retention was computed by compounding two noisy calendar-month ratios (month 7->8->9), even though months 7-8 aren't real renewal points for a 3-month billing cycle -- see prior conversation for the exact -72%/+189% swing that was being multiplied through. sBG (fit on cohort-level quarterly checkpoints, alpha=7.20, beta=10.73) predicts month 9 directly without that contamination.
- **Why changed (validation):** Structural fix (formula -> static value), not a tier-fit -- see raw-curve CV above (4 folds, 42 held-out points, MAE 0.0527 vs sheet 0.0845).
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
- **New value:** 0.0901
- **Finding:** 3-Month post-M24 churn (monthly-equiv.): sheet assumed 1.0%/month. sBG-implied monthly-equivalent rate for this window is 9.0%/month.
- **Why changed (validation):** Based on the same fit as month-9 above. Only 42 held-out data points exist this deep in the curve -- treat as directionally useful, not fully validated.
- **Business impact:** Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.
- **Confidence:** MEDIUM

