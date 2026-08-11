# DITTO Retention Modelling (sBG)

Fits a shifted-Beta-Geometric (sBG) survival model to the Monthly and 3-Month
subscription cohorts, cross-validates it properly (time-series folds, not a
single arbitrary cutoff), derives the sheet-ready flat-tier churn rates, and
generates a report explaining exactly what changed, why, how well it's
validated, and what it does to LTV/CAC.

## Data source

**Only uses the cohort matrices** in the appendix sheets (`APPENDIX Monthly
Subscription R`, `APPENDIX 3-Month Subscription R`) -- the `MONTH 0, MONTH 1,
...` count tables and the `RETENTION` % sub-table. Deliberately does **not**
use the per-subscriber ID/signup/cancellation-date export sitting further
right in those same sheets -- that field isn't reliably maintained.

For 3-Month specifically: billing happens every 3 months, so raw month-by-
month counts are billing-event noise. We resample the sheet's own `RETENTION`
table at the actual quarterly checkpoints (month 0, 3, 6, 9, ...) instead.

## Files

```
data/
  monthly_counts.csv       cohort_month, tenure_months, survivors
  threemonth_counts.csv    cohort_month, tenure_cycles (x3 months), survivors
src/
  extract_data.py          pulls the two CSVs above out of model.xlsx
  sbg_model.py             sBG survival function, MLE fit, log-likelihood
  cross_validate.py        multi-fold time-series CV (expanding window,
                            non-overlapping test windows -- the TimeSeriesSplit
                            equivalent for cohort data)
  business_impact.py       replicates the exact LTV/CAC:LTV formula chain
                            from Cohort Modelling, so we can compute before/
                            after impact without a full workbook recalc
  run_pipeline.py          orchestrates everything -> outputs/report.md +
                            outputs/sheet_updates.csv
outputs/
  report.md                narrative: what changed, why, validation, impact
  sheet_updates.csv         same info, machine-readable
model.xlsx                 source workbook (not committed - see .gitignore)
```

## Running it

```bash
pip install -r requirements.txt

python3 src/extract_data.py     # (re)build the CSVs from model.xlsx
python3 src/run_pipeline.py     # fit + CV + business impact -> outputs/report.md
```

Open `outputs/report.md` and paste the "New value" for each listed cell into
the actual live financial model.

## Important limitation

`business_impact.py` hardcodes a handful of base assumptions (CAC, price,
gross margin) copied from `Cohort Modelling!B1:B12` at the time this was
built. If those change in the sheet, update the constants at the top of that
file to match -- they don't auto-sync.

Similarly, `Cohort Modelling!K415` (the 3-Month month-9 fix) was applied by
hand directly in the workbook already (replacing a formula with a static
value) -- it won't be re-applied by rerunning this pipeline. Rerunning
`run_pipeline.py` will tell you what the *current* fitted value would be, so
you can compare and decide whether to update it again.

## Current results (last run)

**Monthly** -- validated well. Time-series CV (5 folds, 125 held-out points):
new flat-tier numbers MAE 0.0236 vs old sheet numbers MAE 0.0358 (~34% better).
Business impact: 1st Yr LTV moves from £135.07 to £129.46 (worse -- the sheet
was too optimistic about months 7-12).

**3-Month** -- directionally supportive but thinner data (4 folds, 42 held-out
points, ~38% better on aggregate, but individual folds disagree). Month-9 fix
alone: 1st Yr LTV improves £126.83 -> £129.93.

## Next steps

1. Build the Retention Tracker sheet (ML prediction vs current sheet
   prediction vs actual, frozen at generation date) -- not yet built.
2. Re-run monthly as new Klar data lands.

