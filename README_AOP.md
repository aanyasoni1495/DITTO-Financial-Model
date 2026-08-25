# AOP Forecasting (Cash Flow!row17)

Forecasts Average Order Price by combining the retention-model repo's own
live curve (docs/curves.json) with real Shopify order history. Built to
plug into the SAME repo as the sBG retention model -- whenever that model
refits and curves.json changes, this pipeline automatically uses the new
curve. Nothing here is hardcoded.

## Files added

```
src/
  extract_shopify_orders.py    parses raw Shopify order exports, classifies
                                plan type from Appstle Tags (NOT product name
                                -- that changed twice during the export's
                                history), separates first-order vs recurring
  build_customer_cohorts.py    builds subscriber-level "spells": each
                                customer's signup, plan, first-order price
                                paid, and their OWN real recurring price
  detect_price_changes.py      month-by-month dominant list price per plan,
                                from real order data
  estimate_current_mix.py      current active-subscriber mix -- combines
                                real acquisition history with the LIVE
                                retention curve (not raw acquisition-mix,
                                which is a different, misleading number --
                                see "Why not just use last month's
                                acquisition mix" below)
  forecast_aop.py               the actual forecast: subscriber-matched
                                cohort pricing + live retention curve +
                                confirmed real AOP formula
  validate_final.py             time-series backtest + rolling-origin CV
                                against every real historical month
  run_aop_pipeline.py            orchestrates all of the above ->
                                outputs/aop_report.md + aop_cell_updates.csv
data/
  orders_clean.csv              extracted, classified order-level data
  customer_cohorts.csv          subscriber-level cohort/pricing table
  price_history.json            month-by-month dominant price per plan
outputs/
  aop_report.md                 validation results + exact cell updates
  aop_cell_updates.csv           same, machine-readable
```

## Running it

```bash
# One-time / whenever you have a fresh Shopify export:
python3 src/extract_shopify_orders.py data/orders_export_*.csv
python3 src/build_customer_cohorts.py
python3 src/detect_price_changes.py

# Every time the retention model refits (after its own run_pipeline.py +
# export_curves.py regenerate docs/curves.json):
python3 src/run_aop_pipeline.py
```

Open `outputs/aop_report.md`. It lists exactly which `Cash Flow!row17`
months to update, with old (placeholder) vs. new (forecast) values --
real historical months are explicitly marked "do not change."

## Why the AOP formula is what it is (found the hard way -- 3 real bugs)

Confirmed by directly inspecting the sheet's own formulas:
`AOP = Total Revenue / Total Orders` (all orders, all plans, that calendar
month) -- for real months, both are hardcoded actuals; from **2026-08
onward, AOP itself is the hardcoded INPUT** and Revenue is derived from it,
which is why 2026-08's "£41.84" is NOT treated as ground truth anywhere in
this pipeline -- it's already a placeholder guess, same as the months after it.

Three real bugs found and fixed by validating against actual months, in order:
1. **Wrong denominator** -- initially assumed "Monthly Acquisitions" meant
   new signups only; it's actually total orders (new + renewals).
2. **List price vs. actual amount paid** -- discounts are large and common
   (confirmed: July 2026 AOP is £41.87 using real amounts paid, vs £56.81
   if you wrongly use list price). Must use actual paid amount.
3. **First-order discount doesn't carry to renewals** -- confirmed directly:
   subscribers renew at the RECURRING price locked in at signup, not their
   discounted first-order price, and not the CURRENT price either. Fixed
   by matching each subscriber's actual renewal orders (via Email) to get
   their own real recurring price.

## Why current mix isn't just "last month's acquisition mix"

Acquisition mix (new signups only) has swung hard -- from ~4% 3-Month at
launch to ~78% by August 2026. But the ACTIVE base includes everyone who
signed up historically, most of whom joined when Monthly dominated. Using
raw acquisition mix would assume the entire active base already looks like
this month's newest signups, which retention data disproves directly.
`estimate_current_mix.py` instead projects every historical cohort forward
through the live retention curve to estimate who's actually still active
today -- landed at Monthly 34.8% / 3-Month 65.2%, close to the sheet's
existing 30%/65% assumption (a genuinely reassuring, validated finding, not
assumed).

## Validation results (last run)

14 real historical months tested, time-series backtest (never let the
model see the future) + 4-fold rolling-origin cross-validation:

- Average error: 4.2%
- 93% of months within 10% error
- Rolling-origin CV: MAE £1.36-£3.12 across 4 independent folds
- **Confidence: HIGH**

## Known limitation

Mix is held FIXED going forward (matches the sheet's own B8/B9 structure,
which is also a flat constant). An earlier attempt at a mix-shift TREND
model (log-ratio regression, correctly bounded 0-100%) was built and
rejected -- validated at only 14% average error / LOW confidence, too
uncertain given the trend is still accelerating with limited history. That
script is not included here; frozen-current-mix was the deliberate,
validated choice instead.

The forecast oscillates on a 3-month cycle -- this is REAL, not a bug (see
note in aop_report.md): 3-Month subscribers renew quarterly, so months
where more 3-Month cohorts hit their renewal point show higher blended
AOP. This same pattern is present in the real historical data.
