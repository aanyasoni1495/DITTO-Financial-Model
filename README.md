# DITTO Retention Modelling (sBG)

Fits a shifted-Beta-Geometric (sBG) survival model to the Monthly and 3-Month
subscription cohorts, cross-validates it with proper time-series folds,
reads ALL assumptions live from the workbook (no hardcoded prices/mix/curve
values anywhere), and generates a report explaining exactly what changed,
why, how confident that is (with real justification, not just a label), and
what it does to LTV/CAC/Blended AOV.

## Why "read live from the workbook" matters

An earlier version of this pipeline hardcoded assumptions as Python
constants. That caused a real bug: `Model Assumptions!C32` was hardcoded as
0.04 in the code, when the cell actually contains 0.03 -- AND, separately,
that cell turned out to be unused by the live curve entirely (the curve
actually reads `Cohort Modelling!B20`, which genuinely is 0.04). Hardcoding
meant this went unnoticed until manually checked against a screenshot.

`read_model_state.py` fixes this at the root: instead of trying to guess
which input cell drives the curve, it reads the CURVE ITSELF (the computed
output, e.g. `Cohort Modelling!row248`) directly from the workbook every run.
That can't be wrong in the way a hardcoded assumption can, because it's
reading what the sheet is actually doing today, not what we assume it's doing.

## Data source

**Only uses the cohort matrices** in the appendix sheets -- deliberately does
**not** use the per-subscriber cancellation-date export (unreliable field).
3-Month specifically resamples the sheet's own `RETENTION` table at quarterly
checkpoints (0, 3, 6, 9...) rather than raw calendar months.

## Files

```
data/
  monthly_counts.csv        cohort_month, tenure_months, survivors
  threemonth_counts.csv     cohort_month, tenure_cycles (x3 months), survivors
  model_state.json          everything read live from model.xlsx (regenerated each run)
src/
  extract_data.py           pulls the two cohort CSVs above out of model.xlsx
  read_model_state.py       reads ALL assumptions + current live curves from
                             model.xlsx -- nothing hardcoded, see note above
  sbg_model.py               sBG survival function, MLE fit, log-likelihood
  cross_validate.py          multi-fold time-series CV + confidence_rating()
                             (real reasoning, not a heuristic label)
  business_impact.py         LTV/CAC:LTV/Blended AOV formulas, parameterized
                             by the live-read state (no hardcoded constants)
  run_pipeline.py            orchestrates everything -> outputs/report.md
outputs/
  report.md                  narrative: mix, AOV, per-cell findings + confidence
  sheet_updates.csv          same info, machine-readable
model.xlsx                   source workbook (not committed - see .gitignore)
```

## Running it

```bash
pip install -r requirements.txt

python3 src/extract_data.py     # (re)build the CSVs from model.xlsx
python3 src/run_pipeline.py     # fits AND cross-validates BOTH sBG and BdW,
                                 # for BOTH plans, and writes outputs/report.md
```

`run_pipeline.py` is the single source of truth now -- it runs sBG and BdW
for both Monthly and 3-Month, cross-validates each, and picks a winner per
plan based on held-out accuracy (not assumed to be the same model for both
plans -- see the comparison table at the top of the report). Cell values are
shown for both models, with the losing model's rows explicitly marked "not
recommended" rather than removed, so you can see what was considered.

`src/compare_models.py` still exists as a lighter-weight, terminal-only
version of just the head-to-head comparison, if you want to check that
without regenerating the full report.

Open `outputs/report.md`. Every cell listed has an **old value** (or a note
saying it's read live / not directly meaningful, see the C32 case above), a
**new value**, a **finding**, a **confidence rating with a plain-English
reason**, and a **business impact**.

## Confidence ratings, and what actually earns each one

Computed by `confidence_rating()` in `cross_validate.py`:

- **HIGH**: beats the current numbers on held-out data, wins a large majority
  of CV folds, plenty of held-out points, no fold's fit hit the optimizer's
  bounds (a sign of a fold not having enough data to fit reliably)
- **MEDIUM**: beats the current numbers, but on a smaller sample or less
  consistently across folds
- **LOW**: either doesn't beat the current numbers, or at least one fold's
  fit was unstable (hit the optimizer bounds)

This isn't a vibe -- every rating in the report is followed by the actual
numbers (fold win rate, point count, MAE comparison) that produced it.

## BdW comparison (Fader, Hardie, Liu, Davin & Steenburgh, 2018)

`src/bdw_model.py` implements the beta-discrete-Weibull model, sBG's more
flexible sibling (adds one parameter, c, letting an individual's own churn
probability drift over time, not just the population mix). As of this
version, `run_pipeline.py` fits and cross-validates BOTH sBG and BdW for
BOTH plans automatically -- no separate step needed. `src/compare_models.py`
still exists as a lighter, terminal-only version of just the head-to-head
comparison if you don't want to regenerate the full report.

**Result (last run, in `outputs/report.md`'s comparison table):**

- **Monthly**: BdW beats sBG by 3.1% on held-out data (MAE 0.0234 vs 0.0241),
  both HIGH confidence, fitted c=0.93 (close to sBG's implicit c=1) -- a
  small, genuine improvement. **BdW is the recommended model for Monthly.**
- **3-Month**: BdW is 8.8% WORSE than sBG on held-out data (MAE 0.0578 vs
  0.0527), both LOW confidence, and BdW's fits are noticeably more unstable
  fold-to-fold than sBG's own instability there -- the extra parameter is
  overfitting 3-Month's already-thin data. **sBG remains the recommended
  model for 3-Month.**

This is exactly the risk flagged before building BdW: more flexibility only
helps when there's enough data to support it -- confirmed differently for
each plan, not assumed to be the same. Worth re-running this monthly, since
3-Month may eventually have enough mature data for BdW to earn its place too.

## Important limitation: Closing Balance

`business_impact.py` includes `diff_closing_balance()`, but this pipeline
cannot recalculate the full workbook itself (the appendix sheets alone are
too large for a reliable automated recalc in most environments). To get the
Cash Flow impact: paste the new values into your live copy, let Excel
recalculate, save as `model_after.xlsx` (keep the original as
`model_before.xlsx`), then run:

```python
from business_impact import diff_closing_balance
diff_closing_balance('model_before.xlsx', 'model_after.xlsx')
```

## Known pre-existing sheet inconsistency (not fixed by this pipeline)

3-Month revenue-per-customer is computed two different ways in two different
places in the sheet: `Cohort Modelling!row27` (feeds "1st Yr LTV") uses the
£100 list price (`B6`); `row417` (feeds Blended AOV, closer to what reaches
Cash Flow) uses £81 (`B418`), a separate, unlinked "net price" constant.
These disagree by ~19% and nobody has confirmed which is correct. Worth
resolving before trusting LTV/CAC:LTV numbers too far.

## Current results (last run)

**Monthly**: HIGH confidence. 5 folds, 125 held-out points, wins 100% of
folds, no instability. 1st Yr LTV moves £135.07 -> £129.46 (the sheet was
too optimistic about months 7-12).

**3-Month**: LOW confidence -- genuinely improves on held-out data (37.6%
better MAE) but at least one CV fold's fit hit the optimizer's bounds,
signalling not-yet-enough mature cohorts. Revisit as more data lands.

## Next steps

1. Re-run monthly as new Klar data lands -- watch whether 3-Month's
   confidence rating upgrades from LOW as more cohorts mature.
2. Resolve the £81 vs £100 pricing inconsistency above.
3. Get closing balance impact via `diff_closing_balance()` once you have
   before/after recalculated files.

