# Retention Model Update -- sBG vs BdW, Both Plans

All assumptions (prices, mix, CAC, current curves) were read live from `model.xlsx` at run time. Both models are fit and cross-validated for both plans; each plan uses whichever model actually wins on held-out accuracy for that plan -- they are not assumed to be the same.

## Current plan mix (unaffected by any model choice)

- Monthly: 30%
- 3-Month: 65%
- 6-Month: 0%
- OTP: 5%

## Model comparison, by plan

| Plan | sBG MAE | sBG confidence | BdW MAE | BdW confidence | Winner | Margin |
|---|---|---|---|---|---|---|
| Monthly | 0.0241 | HIGH | 0.0234 | HIGH | **BdW** | 3.1% |
| 3-Month | 0.0527 | LOW | 0.0579 | LOW | **sBG** | 9.0% |

## Cell-by-cell values -- one row per cell, both models shown

| Plan | Cell | Old value | sBG value | BdW value | Winner | Recommended value |
|---|---|---|---|---|---|---|
| Monthly | `Model Assumptions!C32` | (read live from sheet) | 0.0979 | 0.1035 | **BdW** | 0.1035 |
| Monthly | `Cohort Modelling!B20` | 0.0300 | 0.0979 | 0.1035 | **BdW** | 0.1035 |
| Monthly | `Model Assumptions!C33` | (read live from sheet) | 0.0575 | 0.0635 | **BdW** | 0.0635 |
| Monthly | `Model Assumptions!C34` | (read live from sheet) | 0.0315 | 0.0360 | **BdW** | 0.0360 |
| 3-Month | `Cohort Modelling!K415 (I415, J415 flattened to =H415)` | 0.1952 (via noisy compounded formula) | 0.236565 | 0.239111 | **sBG** | 0.236565 |
| 3-Month | `Model Assumptions!C43` | (read live) | 0.1312 | 0.0961 | **sBG** | 0.1312 |
| 3-Month | `Model Assumptions!C44` | (read live) | 0.1156 | 0.0626 | **sBG** | 0.1156 |
| 3-Month | `Model Assumptions!C45` | (read live) | 0.0901 | 0.0330 | **sBG** | 0.0901 |

**Use the 'Recommended value' column when pasting into the sheet.** The 'sBG value' and 'BdW value' columns are both shown for transparency -- only one of them (matching 'Winner') is actually recommended per plan.

## Confidence rating key

- **HIGH**: beats current numbers on held-out data, wins a large majority of CV folds, plenty of held-out points, no fit instability
- **MEDIUM**: beats current numbers, but on a smaller sample or less consistently
- **LOW**: either doesn't beat current numbers, or the fit was unstable in at least one fold (a sign of insufficient data, common for BdW's extra parameter on the 3-Month plan specifically)

## Detail per cell

### [Monthly] `Model Assumptions!C32`

- **Old value:** (read live from sheet)
- **sBG value:** 0.0979 (confidence: HIGH)
- **BdW value:** 0.1035 (confidence: HIGH)
- **Winner: BdW** -- BdW won held-out cross-validation: sBG MAE=0.0241 (HIGH) vs BdW MAE=0.0234 (HIGH), by 3.1%. Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Recommended value (use this): 0.1035**
- **Finding:** Monthly M7-12 churn.
- **Business impact:** sBG: 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS | BdW: 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

### [Monthly] `Cohort Modelling!B20`

- **Old value:** 0.0300
- **sBG value:** 0.0979 (confidence: HIGH)
- **BdW value:** 0.1035 (confidence: HIGH)
- **Winner: BdW** -- BdW won held-out cross-validation: sBG MAE=0.0241 (HIGH) vs BdW MAE=0.0234 (HIGH), by 3.1%. Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Recommended value (use this): 0.1035**
- **Finding:** Monthly M7-12 churn (cell the live curve actually uses).
- **Business impact:** sBG: 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS | BdW: 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

### [Monthly] `Model Assumptions!C33`

- **Old value:** (read live from sheet)
- **sBG value:** 0.0575 (confidence: HIGH)
- **BdW value:** 0.0635 (confidence: HIGH)
- **Winner: BdW** -- BdW won held-out cross-validation: sBG MAE=0.0241 (HIGH) vs BdW MAE=0.0234 (HIGH), by 3.1%. Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Recommended value (use this): 0.0635**
- **Finding:** Monthly M13-24 churn.
- **Business impact:** sBG: 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS | BdW: 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

### [Monthly] `Model Assumptions!C34`

- **Old value:** (read live from sheet)
- **sBG value:** 0.0315 (confidence: HIGH)
- **BdW value:** 0.0360 (confidence: HIGH)
- **Winner: BdW** -- BdW won held-out cross-validation: sBG MAE=0.0241 (HIGH) vs BdW MAE=0.0234 (HIGH), by 3.1%. Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Recommended value (use this): 0.0360**
- **Finding:** Monthly post-M24 churn.
- **Business impact:** sBG: 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS | BdW: 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

### [3-Month] `Cohort Modelling!K415 (I415, J415 flattened to =H415)`

- **Old value:** 0.1952 (via noisy compounded formula)
- **sBG value:** 0.236565 (confidence: LOW)
- **BdW value:** 0.239111 (confidence: LOW)
- **Winner: sBG** -- sBG won held-out cross-validation: sBG MAE=0.0527 (LOW) vs BdW MAE=0.0579 (LOW), by 9.0%. Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Recommended value (use this): 0.236565**
- **Finding:** 3-Month month-9 retention.
- **Business impact:** sBG: 1st Yr LTV: £126.83 -> £129.93 (IMPROVES); CAC:LTV IMPROVES | BdW: 1st Yr LTV: £126.83 -> £130.12 (IMPROVES); CAC:LTV IMPROVES

### [3-Month] `Model Assumptions!C43`

- **Old value:** (read live)
- **sBG value:** 0.1312 (confidence: LOW)
- **BdW value:** 0.0961 (confidence: LOW)
- **Winner: sBG** -- sBG won held-out cross-validation: sBG MAE=0.0527 (LOW) vs BdW MAE=0.0579 (LOW), by 9.0%. Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Recommended value (use this): 0.1312**
- **Finding:** 3-Month M7-12 churn (monthly-equiv.).
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

### [3-Month] `Model Assumptions!C44`

- **Old value:** (read live)
- **sBG value:** 0.1156 (confidence: LOW)
- **BdW value:** 0.0626 (confidence: LOW)
- **Winner: sBG** -- sBG won held-out cross-validation: sBG MAE=0.0527 (LOW) vs BdW MAE=0.0579 (LOW), by 9.0%. Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Recommended value (use this): 0.1156**
- **Finding:** 3-Month M13-24 churn (monthly-equiv.).
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

### [3-Month] `Model Assumptions!C45`

- **Old value:** (read live)
- **sBG value:** 0.0901 (confidence: LOW)
- **BdW value:** 0.0330 (confidence: LOW)
- **Winner: sBG** -- sBG won held-out cross-validation: sBG MAE=0.0527 (LOW) vs BdW MAE=0.0579 (LOW), by 9.0%. Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Recommended value (use this): 0.0901**
- **Finding:** 3-Month post-M24 churn (monthly-equiv.).
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

