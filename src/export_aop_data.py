"""
Exports docs/aop_data.json -- the data file the Netlify AOP Forecast page
(docs/aop_forecast.html) reads to render the Cash Flow!row17 forecast and
let a person try a hypothetical NEW-signup price/discount/mix (Monthly,
3-Month, OTP -- same three inputs as the AOV Simulator) in the browser.

IMPORTANT -- why this reads model.xlsx directly instead of using a
hardcoded date list:
  Earlier versions of this script hardcoded which months are "real" (from
  validate_final.REAL_HISTORICAL_AOP) and a fixed forecast end date
  ("2029-03"). That drifts out of sync with the actual sheet -- checked
  directly against a real row17 paste from the sheet, and the columns did
  not line up past a certain point. The sheet itself already tells us
  everything we need: a FORMULA cell in row17 is a real, already-computed
  month; a plain hardcoded number is a placeholder guess. This script
  reads that distinction live, every run, straight from model.xlsx, so
  the exported real/forecast boundary and the full column range always
  match the sheet exactly -- no separate list to maintain or drift.
  Requires model.xlsx to be present (it is, at this point in the
  automation pipeline, before the later cleanup step deletes it).

What changed vs the fixed recommendation in run_aop_pipeline.py:
  run_aop_pipeline.py still answers "what should row17 say" (one grounded
  recommendation, using the SHEET's own forecasted plan mix and August's
  real average price -- unchanged, still the validated 4.8%-error model).
  This script instead exports each forecast month's PIECES so a person
  can try their OWN hypothetical new-signup price/discount/mix on top of
  the same real renewal base:
    - renewal_orders / renewal_revenue: real subscribers who already
      signed up, renewing at their OWN real locked-in price. Never
      hypothetical -- a person can't change what a past subscriber
      already agreed to pay, and this script doesn't let them try.
    - total_new_signups: the sheet's own forecasted count of brand-new
      customers that month (Revenue Model!row9/row10 combined). This
      TOTAL is fixed -- not something this tool second-guesses. What IS
      left to the person is how that fixed volume splits across Monthly /
      3-Month / OTP, and what each plan charges (with an optional
      first-purchase discount on Monthly/3-Month, matching the AOV
      Simulator) -- exactly the inputs the AOV Simulator already uses.

Known simplification (shared with the underlying validated model): a
hypothetical new signup created during a FORECAST month doesn't generate
its own future renewals in this tool -- only real historical cohorts
renew going forward. Same limitation forecast_aop.py already has; not
introduced by this script.

Usage:
    python3 src/export_aop_data.py
"""
import json
from collections import defaultdict
from datetime import datetime, timezone

from forecast_aop import (load_cohorts, load_price_history, load_sheet_acquisition_forecast,
                           resolve_recurring_price, month_index)
from validate_final import REAL_HISTORICAL_AOP, run_backtest
import forecast_aop as fa


def month_label(idx):
    y, m = idx // 12, idx % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y}-{m:02d}"


def load_full_row17(xlsx_path="model.xlsx"):
    """
    Reads EVERY column of Cash Flow!row17 directly from the live sheet --
    both the computed value (data_only=True workbook) and whether that
    cell holds a formula or a plain hardcoded number (data_only=False
    workbook). A formula cell means the month is real and already
    computed by the sheet itself -- kept exactly as-is, never touched. A
    plain number means it's a hand-typed placeholder guess -- exactly the
    kind of cell this tool is meant to help replace.

    Returns an ordered list of {month, is_real, sheet_value}, sorted by
    date, covering the sheet's actual full range -- whatever that
    currently is. Returns [] if model.xlsx isn't present (e.g. running
    this script outside the automation pipeline, with no workbook on
    hand) -- callers should fall back to a smaller hardcoded range in
    that case, clearly logged, rather than silently exporting nothing.
    """
    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed -- cannot read model.xlsx")
        return []

    try:
        wb_values = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
        wb_formulas = openpyxl.load_workbook(xlsx_path, data_only=False, read_only=True)
    except FileNotFoundError:
        print(f"'{xlsx_path}' not found -- cannot read the live row17 range. "
              f"Falling back to a smaller hardcoded range (see run()).")
        return []

    ws_values = wb_values["Cash Flow"]
    ws_formulas = wb_formulas["Cash Flow"]

    date_row = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True))
    value_row = next(ws_values.iter_rows(min_row=17, max_row=17, values_only=True))
    formula_row = next(ws_formulas.iter_rows(min_row=17, max_row=17, values_only=True))

    columns = []
    for d, val, raw in zip(date_row, value_row, formula_row):
        if d is None or not hasattr(d, "strftime"):
            continue
        is_formula = isinstance(raw, str) and raw.startswith("=")
        columns.append({
            "month": d.strftime("%Y-%m"),
            "is_real": is_formula,
            "sheet_value": round(float(val), 4) if isinstance(val, (int, float)) else None,
        })

    columns.sort(key=lambda c: month_index(c["month"]))
    return columns


def decompose_month(spells, forecast_month_idx, curves, price_history, sheet_acquisitions):
    """
    Real renewal orders/revenue (from actual past cohorts, unchanged) plus
    the sheet's own total forecasted new-signup COUNT for this month
    (Monthly + 3-Month combined). The front-end takes this fixed total and
    splits/prices it however the person chooses (Monthly/3-Month/OTP mix
    and price, with an optional first-purchase discount) -- this function
    doesn't assume any particular split itself.
    """
    acquisitions_by_month_plan = defaultdict(lambda: defaultdict(list))
    for spell in spells:
        if month_index(spell["signup_month"]) >= forecast_month_idx:
            continue
        acquisitions_by_month_plan[spell["plan"]][spell["signup_month"]].append(spell)

    renewal_orders = 0.0
    renewal_revenue = 0.0
    forecast_label = month_label(forecast_month_idx)
    sheet_acq_this_month = sheet_acquisitions.get(forecast_label, {})

    for plan, cycle_len, curve_key in [
        ("Monthly", 1, "monthly_curve"),
        ("3-Month", 3, "threemonth_curve_cycles"),
    ]:
        curve = curves[curve_key]
        for signup_month, cohort_spells in acquisitions_by_month_plan[plan].items():
            signup_idx = month_index(signup_month)
            months_since_signup = forecast_month_idx - signup_idx
            if months_since_signup <= 0 or months_since_signup % cycle_len != 0:
                continue
            units = months_since_signup // cycle_len
            retention = curve[units] if units < len(curve) else curve[-1]
            n = len(cohort_spells)
            still_active = n * retention
            avg_recurring_price = sum(
                resolve_recurring_price(s, price_history) or 0 for s in cohort_spells
            ) / n
            renewal_orders += still_active
            renewal_revenue += still_active * avg_recurring_price

    total_new_signups = (sheet_acq_this_month.get("monthly", 0) +
                          sheet_acq_this_month.get("threemonth", 0))

    return {
        "renewal_orders": round(renewal_orders, 2),
        "renewal_revenue": round(renewal_revenue, 2),
        "total_new_signups": round(total_new_signups, 2),
    }


def run():
    with open("docs/curves.json") as f:
        curves = json.load(f)

    spells = load_cohorts("data/customer_cohorts.csv")
    price_history = load_price_history("data/price_history.json")
    sheet_acquisitions = load_sheet_acquisition_forecast("data/sheet_acquisition_forecast.json")

    # Confidence score -- still validated against the known-real historical
    # months (unchanged, still the trusted 4.8%-error backtest)
    test_months = sorted(REAL_HISTORICAL_AOP.keys())
    results = run_backtest(spells, curves, price_history, test_months, min_history_months=3)
    if results:
        avg_pct = sum(r["pct_err"] for r in results) / len(results)
        win_rate = sum(1 for r in results if r["pct_err"] < 10) / len(results)
        confidence = ("HIGH" if avg_pct < 8 and win_rate > 0.8 else
                      "MEDIUM" if avg_pct < 20 and win_rate > 0.5 else "LOW")
    else:
        confidence, avg_pct = "LOW", None

    row17 = load_full_row17("model.xlsx")

    months = []
    if row17:
        # Live sheet available -- use its ACTUAL full range and its own
        # formula-vs-literal distinction. This is the accurate path,
        # used every time the automation runs for real.
        last_real_month = max((c["month"] for c in row17 if c["is_real"]), key=month_index)
        print(f"Read live row17 from model.xlsx: {row17[0]['month']} to {row17[-1]['month']}, "
              f"last real month = {last_real_month}")
        for col in row17:
            if col["is_real"]:
                months.append({
                    "month": col["month"],
                    "is_real": True,
                    "actual_aop": col["sheet_value"],
                })
            else:
                idx = month_index(col["month"])
                pieces = decompose_month(spells, idx, curves, price_history, sheet_acquisitions)
                months.append({
                    "month": col["month"],
                    "is_real": False,
                    "current_sheet_value": col["sheet_value"],
                    **pieces,
                })
    else:
        # Fallback -- no model.xlsx on hand (e.g. testing locally without
        # the workbook). Covers only the previously-validated real months
        # plus a fixed 32-month forecast window, so the page still works,
        # just with a narrower range than the live sheet actually has.
        print("No model.xlsx -- using fallback range (validated real months + 32 forecast months). "
              "Re-run inside the automation pipeline (where model.xlsx is present) for the full, "
              "exact column range matching the live sheet.")
        last_real_month = max(REAL_HISTORICAL_AOP.keys(), key=month_index)
        last_real_idx = month_index(last_real_month)
        for m in sorted(REAL_HISTORICAL_AOP.keys(), key=month_index):
            months.append({"month": m, "is_real": True, "actual_aop": REAL_HISTORICAL_AOP[m]})
        for i in range(1, 33):
            idx = last_real_idx + i
            label = month_label(idx)
            pieces = decompose_month(spells, idx, curves, price_history, sheet_acquisitions)
            months.append({"month": label, "is_real": False, "current_sheet_value": None, **pieces})

    data = {
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "last_real_month": last_real_month,
        "confidence": confidence,
        "avg_error_pct": round(avg_pct, 1) if avg_pct is not None else None,
        "full_range_from_live_sheet": bool(row17),
        # Read fresh from the module (not imported by name at the top of
        # this file) -- run_backtest temporarily overwrites this dict's
        # contents while testing historical months, and its "restore"
        # step reassigns the module attribute rather than mutating back
        # in place, so a name bound at import time would keep pointing at
        # a stale, mutated value. Accessing it via fa.AUGUST_AVG_PRICE
        # here, after run_backtest has already finished, avoids that.
        "baseline_new_signup_price": {
            "monthly": round(fa.AUGUST_AVG_PRICE["Monthly"], 2),
            "threemonth": round(fa.AUGUST_AVG_PRICE["3-Month"], 2),
        },
        "months": months,
    }

    with open("docs/aop_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote docs/aop_data.json -- {len(months)} months "
          f"({sum(1 for m in months if m['is_real'])} real, "
          f"{sum(1 for m in months if not m['is_real'])} forecast)")


if __name__ == "__main__":
    run()
