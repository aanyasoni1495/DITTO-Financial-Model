"""
Exports docs/aop_data.json -- the data file the Netlify AOP Forecast page
(docs/aop_forecast.html) reads to render the Cash Flow!row17 forecast and
let a person try hypothetical NEW-SIGNUP prices/mix in the browser.

Why this is a separate file from run_aop_pipeline.py:
  run_aop_pipeline.py answers "what should the sheet's row17 say" (one
  fixed recommendation, written to outputs/). This script answers "let a
  person explore variations" -- so instead of one number per month, it
  exports each month's PIECES:
    - renewal_orders / renewal_revenue: real subscribers who already
      signed up, renewing at their OWN real locked-in price. This part is
      never hypothetical -- a person can't change what a past subscriber
      already agreed to pay.
    - new_signups_monthly / new_signups_threemonth: the sheet's own
      forecasted count of brand-new signups that month (fixed volume --
      comes from Revenue Model!row9/row10, not something this tool
      second-guesses), split by plan.
  The front-end then combines: hypothetical_new_signup_price * that
  month's new-signup volume (redistributed across plans by the person's
  chosen mix, total held fixed) + the fixed renewal piece = hypothetical
  blended AOP for that month. This mirrors the AOV Simulator's existing
  pattern (hypothetical price/mix, but retention/renewals held real).

Usage:
    python3 src/export_aop_data.py
"""
import json
from collections import defaultdict
from datetime import date, datetime, timezone

import forecast_aop as fa
from forecast_aop import (load_cohorts, load_price_history, load_sheet_acquisition_forecast,
                           resolve_recurring_price, month_index, month_label)
from estimate_current_mix import load_monthly_acquisitions, estimate_active
from validate_final import run_backtest, REAL_HISTORICAL_AOP

FORECAST_END_MONTH = "2029-03"  # keep in sync with run_aop_pipeline.py


def get_live_mix(curves):
    acquisitions = load_monthly_acquisitions("data/orders_clean.csv")
    today = date.today()
    today_idx = today.year * 12 + today.month
    active_m = estimate_active(acquisitions["Monthly"], curves["monthly_curve"],
                                today_idx, cycle_length_months=1)
    active_3 = estimate_active(acquisitions["3-Month"], curves["threemonth_curve_cycles"],
                                today_idx, cycle_length_months=3)
    total = active_m + active_3
    if total == 0:
        return None, None
    return active_m / total, active_3 / total


def decompose_month(spells, forecast_month_idx, curves, price_history, sheet_acquisitions):
    """Same math as forecast_aop.forecast_aop, but returns the renewal and
    new-signup pieces SEPARATELY instead of one blended number, so the
    front-end can recombine them with a hypothetical new-signup price/mix."""
    acquisitions_by_month_plan = defaultdict(lambda: defaultdict(list))
    for spell in spells:
        if month_index(spell["signup_month"]) >= forecast_month_idx:
            continue
        acquisitions_by_month_plan[spell["plan"]][spell["signup_month"]].append(spell)

    renewal_orders = 0.0
    renewal_revenue = 0.0
    new_signups = {}
    forecast_label = month_label(forecast_month_idx)
    sheet_acq_this_month = sheet_acquisitions.get(forecast_label, {})

    for plan, cycle_len, curve_key, sheet_key in [
        ("Monthly", 1, "monthly_curve", "monthly"),
        ("3-Month", 3, "threemonth_curve_cycles", "threemonth"),
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

        new_signups[sheet_key] = sheet_acq_this_month.get(sheet_key, 0)

    return {
        "renewal_orders": round(renewal_orders, 2),
        "renewal_revenue": round(renewal_revenue, 2),
        "new_signups_monthly": round(new_signups.get("monthly", 0), 2),
        "new_signups_threemonth": round(new_signups.get("threemonth", 0), 2),
    }


def load_current_row17_values(xlsx_path="model.xlsx"):
    """Same helper as run_aop_pipeline.py -- reads real old sheet values if
    model.xlsx happens to be present at export time. Not required."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    except Exception:
        return {}
    ws = wb["Cash Flow"]
    rows = list(ws.iter_rows(values_only=True))
    dates, aop_row = rows[0], rows[16]
    values = {}
    for i, d in enumerate(dates):
        if d is not None and hasattr(d, "strftime") and i < len(aop_row):
            values[d.strftime("%Y-%m")] = aop_row[i]
    return values


def run():
    with open("docs/curves.json") as f:
        curves = json.load(f)

    spells = load_cohorts("data/customer_cohorts.csv")
    price_history = load_price_history("data/price_history.json")
    sheet_acquisitions = load_sheet_acquisition_forecast("data/sheet_acquisition_forecast.json")
    mix_m, mix_3 = get_live_mix(curves)

    test_months = sorted(REAL_HISTORICAL_AOP.keys())
    results = run_backtest(spells, curves, price_history, test_months, min_history_months=3)
    if results:
        avg_pct = sum(r["pct_err"] for r in results) / len(results)
        win_rate = sum(1 for r in results if r["pct_err"] < 10) / len(results)
        confidence = ("HIGH" if avg_pct < 8 and win_rate > 0.8 else
                      "MEDIUM" if avg_pct < 20 and win_rate > 0.5 else "LOW")
    else:
        confidence, avg_pct = "LOW", None

    last_real_month = max(REAL_HISTORICAL_AOP.keys(), key=month_index)
    last_real_idx = month_index(last_real_month)
    end_idx = month_index(FORECAST_END_MONTH)
    current_values = load_current_row17_values("model.xlsx")

    months = []

    # Real historical months -- shown for chart context, never editable
    for m in sorted(REAL_HISTORICAL_AOP.keys(), key=month_index):
        months.append({
            "month": m,
            "is_real": True,
            "actual_aop": REAL_HISTORICAL_AOP[m],
        })

    # Forecast months -- decomposed so the front-end can recompute a
    # hypothetical new-signup price/mix while keeping renewals real
    for i in range(1, end_idx - last_real_idx + 1):
        idx = last_real_idx + i
        label = month_label(idx)
        pieces = decompose_month(spells, idx, curves, price_history, sheet_acquisitions)
        old_v = current_values.get(label)
        try:
            old_v = round(float(old_v), 2) if old_v is not None else None
        except (TypeError, ValueError):
            old_v = None
        months.append({
            "month": label,
            "is_real": False,
            "current_sheet_value": old_v,
            **pieces,
        })

    data = {
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "last_real_month": last_real_month,
        "confidence": confidence,
        "avg_error_pct": round(avg_pct, 1) if avg_pct is not None else None,
        "current_mix": {
            "monthly": round(mix_m, 4) if mix_m is not None else None,
            "threemonth": round(mix_3, 4) if mix_3 is not None else None,
        },
        # Read fresh from the module AFTER run_backtest has finished and
        # restored it -- run_backtest temporarily overwrites this dict's
        # contents in place while testing historical months, and its
        # "restore" step reassigns the module attribute rather than
        # mutating back in place, so any name bound via
        # `from forecast_aop import AUGUST_AVG_PRICE` at import time would
        # keep pointing at the stale mutated dict. Accessing it fresh via
        # `fa.AUGUST_AVG_PRICE` here avoids that.
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
