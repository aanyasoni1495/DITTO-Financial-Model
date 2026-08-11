# Retention Model Update -- sBG vs BdW, Both Plans

All assumptions (prices, mix, CAC, current curves) were read live from `model.xlsx` at run time. Both models are fit and cross-validated for both plans; each plan's comparison section recommends whichever model actually wins on held-out accuracy for that plan -- they are not assumed to be the same.

## Current plan mix (unaffected by any model choice)

- Monthly: 30%
- 3-Month: 65%
- 6-Month: 0%
- OTP: 5%

## Model comparison, side by side

| Plan | sBG MAE | sBG confidence | BdW MAE | BdW confidence | Winner | Margin |
|---|---|---|---|---|---|---|
| Monthly | 0.0241 | HIGH | 0.0234 | HIGH | **BdW** | 3.1% |
| 3-Month | 0.0527 | LOW | 0.0579 | LOW | **sBG** | 9.0% |

**Recommendation:** use each plan's winning model's cell values below (marked RECOMMENDED); ignore the other model's rows for actual sheet updates -- they're shown for transparency, not for use.

## Confidence rating key

- **HIGH**: beats current numbers on held-out data, wins a large majority of CV folds, plenty of held-out points, no fit instability
- **MEDIUM**: beats current numbers, but on a smaller sample or less consistently
- **LOW**: either doesn't beat current numbers, or the fit was unstable in at least one fold (a sign of insufficient data, common for BdW's extra parameter on the 3-Month plan specifically)

## [Monthly] `Model Assumptions!C32` -- sBG (not recommended -- see comparison)

- **Old value:** (read live from sheet)
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn: fit params [1.20896786 2.88209189] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0241 vs 0.0390), won 80% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Cohort Modelling!B20` -- sBG (not recommended -- see comparison)

- **Old value:** 0.0300
- **New value:** 0.0979
- **Finding:** Monthly M7-12 churn (cell the live curve actually uses): fit params [1.20896786 2.88209189] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0241 vs 0.0390), won 80% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Model Assumptions!C33` -- sBG (not recommended -- see comparison)

- **Old value:** (read live from sheet)
- **New value:** 0.0575
- **Finding:** Monthly M13-24 churn: fit params [1.20896786 2.88209189] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0241 vs 0.0390), won 80% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Model Assumptions!C34` -- sBG (not recommended -- see comparison)

- **Old value:** (read live from sheet)
- **New value:** 0.0315
- **Finding:** Monthly post-M24 churn: fit params [1.20896786 2.88209189] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0241 vs 0.0390), won 80% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £129.46 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Model Assumptions!C32` -- BdW (RECOMMENDED)

- **Old value:** (read live from sheet)
- **New value:** 0.1035
- **Finding:** Monthly M7-12 churn: fit params [1.57812387 3.71111231 0.92884454] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Cohort Modelling!B20` -- BdW (RECOMMENDED)

- **Old value:** 0.0300
- **New value:** 0.1035
- **Finding:** Monthly M7-12 churn (cell the live curve actually uses): fit params [1.57812387 3.71111231 0.92884454] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Model Assumptions!C33` -- BdW (RECOMMENDED)

- **Old value:** (read live from sheet)
- **New value:** 0.0635
- **Finding:** Monthly M13-24 churn: fit params [1.57812387 3.71111231 0.92884454] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

## [Monthly] `Model Assumptions!C34` -- BdW (RECOMMENDED)

- **Old value:** (read live from sheet)
- **New value:** 0.0360
- **Finding:** Monthly post-M24 churn: fit params [1.57812387 3.71111231 0.92884454] on 153 real data points.
- **Confidence: HIGH** -- Improved on aggregate (0.0234 vs 0.0390), won 100% of 5 folds, 125 held-out points, no fold hit an optimizer bound. Consistent, well-supported result.
- **Business impact:** 1st Yr LTV: £136.13 -> £128.97 (WORSENS); CAC:LTV WORSENS

## [3-Month] `Cohort Modelling!K415 (I415, J415 flattened to =H415)` -- sBG (RECOMMENDED)

- **Old value:** 0.1952 (via noisy compounded formula)
- **New value:** 0.236565
- **Finding:** 3-Month month-9 retention: fit params [ 7.20459018 10.72482574] on 57 real data points.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** 1st Yr LTV: £126.83 -> £129.93 (IMPROVES); CAC:LTV IMPROVES

## [3-Month] `Model Assumptions!C43` -- sBG (RECOMMENDED)

- **Old value:** (read live)
- **New value:** 0.1312
- **Finding:** 3-Month M7-12 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

## [3-Month] `Model Assumptions!C44` -- sBG (RECOMMENDED)

- **Old value:** (read live)
- **New value:** 0.1156
- **Finding:** 3-Month M13-24 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

## [3-Month] `Model Assumptions!C45` -- sBG (RECOMMENDED)

- **Old value:** (read live)
- **New value:** 0.0901
- **Finding:** 3-Month post-M24 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0527 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

## [3-Month] `Cohort Modelling!K415 (I415, J415 flattened to =H415)` -- BdW (not recommended -- see comparison)

- **Old value:** 0.1952 (via noisy compounded formula)
- **New value:** 0.239111
- **Finding:** 3-Month month-9 retention: fit params [0.71558546 1.08291389 1.65306791] on 57 real data points.
- **Confidence: LOW** -- Aggregate MAE improved (0.0579 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** 1st Yr LTV: £126.83 -> £130.12 (IMPROVES); CAC:LTV IMPROVES

## [3-Month] `Model Assumptions!C43` -- BdW (not recommended -- see comparison)

- **Old value:** (read live)
- **New value:** 0.0961
- **Finding:** 3-Month M7-12 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0579 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

## [3-Month] `Model Assumptions!C44` -- BdW (not recommended -- see comparison)

- **Old value:** (read live)
- **New value:** 0.0626
- **Finding:** 3-Month M13-24 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0579 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

## [3-Month] `Model Assumptions!C45` -- BdW (not recommended -- see comparison)

- **Old value:** (read live)
- **New value:** 0.0330
- **Finding:** 3-Month post-M24 churn (monthly-equiv.): derived from the same fit as month-9 above.
- **Confidence: LOW** -- Aggregate MAE improved (0.0579 vs 0.0845), but at least one fold's fit hit the optimizer's bound (alpha or beta pushed to an extreme value) -- a sign that fold simply didn't have enough training data yet for a stable fit. Treat as directionally useful, not settled.
- **Business impact:** Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.

