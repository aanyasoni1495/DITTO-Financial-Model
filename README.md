# DITTO Retention Modelling (sBG)

Fits a shifted-Beta-Geometric (sBG) survival model to the Monthly and 3-Month
subscription cohorts, to replace the hand-tuned retention curve currently in
`Cohort Modelling` / `Model Assumptions` of the DITTO financial model.

## Data source

**Only uses the cohort matrices** in the appendix sheets (`APPENDIX Monthly
Subscription R`, `APPENDIX 3-Month Subscription R`) — the `MONTH 0, MONTH 1,
...` count tables and the `RETENTION` % sub-table. It deliberately does **not**
use the per-subscriber ID/signup/cancellation-date export that sits further
right in those same sheets — that field isn't reliably maintained.

For the 3-Month plan specifically: since billing happens every 3 months, raw
month-by-month counts are billing-event noise (a customer "ships" once but
that showed up in whichever exact calendar month the charge landed). We
resample the sheet's own `RETENTION` % table at the actual quarterly
checkpoints (month 0, 3, 6, 9, ...) rather than at every calendar month —
this is the same quarterly-checkpoint logic the existing Cohort Modelling tab
already uses for its 3-Month curve, just fitted with sBG instead of hand-tuned.

## Files

```
data/
  monthly_counts.csv       cohort_month, tenure_months, survivors
  threemonth_counts.csv    cohort_month, tenure_cycles (x3 months), survivors
src/
  extract_data.py          pulls the two CSVs above out of model.xlsx
  sbg_model.py             sBG survival function, MLE fit, log-likelihood
  run_backtest.py          fits both segments + walk-forward backtest vs the
                           current hand-tuned sheet curve
outputs/
  monthly_sbg_curve.csv    fitted survival curve, month 0-48
  threemonth_sbg_curve.csv fitted survival curve, cycle 0-16 (= month 0-48)
model.xlsx                 source workbook (not committed - see .gitignore)
```

## Running it

```bash
pip install openpyxl numpy scipy

python3 src/extract_data.py     # (re)build the CSVs from model.xlsx
python3 src/run_backtest.py     # fit + backtest, prints results
```

## Current results (as of last run)

**Monthly** — validated. Walk-forward backtest on 70 held-out cohort-month
points: sBG MAE 0.0246 vs current sheet curve MAE 0.0387 (sBG wins by ~35%).

**3-Month** — full-data fit looks reasonable, but the walk-forward backtest is
unstable (only 17 cohorts at quarterly resolution → too few held-out points,
fitted alpha/beta swing depending on cutoff choice). Treat the 3-Month curve
as provisional until another month or two of data lets the backtest run on
more held-out points.

## Next steps

1. Re-run `run_backtest.py` monthly as new Klar data lands (`extract_data.py`
   will need updating if the appendix sheet layout changes).
2. Once 3-Month backtest stabilises, write both curves into
   `Model Assumptions` (replacing the hand-typed retention inputs) and
   `Cohort Modelling`, and recalc.
3. Build the Retention Tracker sheet (ML prediction vs current sheet
   prediction vs actual, frozen at generation date) — not yet built.
