"""
The final, real AOP forecasting model: subscriber-level cohort matching
(build_customer_cohorts.py) + validated retention curves (curves.json) +
the confirmed real AOP formula (Revenue / Total Orders).

For each subscriber's recurring price:
  1. If we've observed at least one of THEIR OWN real renewals, use the
     average of those (most accurate -- their actual price).
  2. Otherwise, fall back to that signup month's dominant list price
     (from detect_price_changes.py) -- confirmed necessary because a
     discounted first-order amount is NOT a valid stand-in for what they'll
     actually pay at renewal (checked directly: cohorts with known renewals
     pay ~£33-38/month; their own first-order-paid average is only ~£20,
     entirely a discount artifact).

Usage:
    python3 src/forecast_aop.py
"""
import csv
import json
from collections import defaultdict


def month_index(m):
    y, mo = m.split("-")
    return int(y) * 12 + int(mo)


def month_label(idx):
    y, mo = idx // 12, idx % 12
    if mo == 0:
        y -= 1
        mo = 12
    return f"{y}-{mo:02d}"


def load_cohorts(path):
    spells = []
    with open(path) as f:
        for row in csv.DictReader(f):
            spells.append(dict(
                email=row["email"], plan=row["plan"], signup_month=row["signup_month"],
                first_order_paid=float(row["first_order_paid"]),
                recurring_price=float(row["recurring_price"]) if row["recurring_price"] else None,
            ))
    return spells


def load_price_history(path):
    with open(path) as f:
        return json.load(f)


def resolve_recurring_price(spell, price_history):
    if spell["recurring_price"] is not None:
        return spell["recurring_price"]
    plan_key = "monthly" if spell["plan"] == "Monthly" else "threemonth"
    hist = price_history.get(plan_key, {})
    if spell["signup_month"] in hist:
        return hist[spell["signup_month"]]["price"]
    # fall back to nearest earlier month with known price
    known_months = sorted(hist.keys())
    earlier = [m for m in known_months if m <= spell["signup_month"]]
    if earlier:
        return hist[earlier[-1]]["price"]
    return None


def load_sheet_acquisition_forecast(path):
    with open(path) as f:
        return json.load(f)


AUGUST_AVG_PRICE = {
    # Real August 2026 average first-order price paid, per plan --
    # confirmed directly from customer_cohorts.csv (n=848 Monthly, n=3015
    # 3-Month signups that month). Used as the FIXED price for every future
    # new signup in the forecast, per explicit instruction -- not the sheet's
    # list price, and not "last known month" (which would silently drift as
    # more real months become available; August is deliberately pinned).
    "Monthly": 19.348172,
    "3-Month": 46.650935,
}


def forecast_aop(spells, forecast_month_idx, curves, price_history,
                  sheet_acquisitions, cutoff_month_idx=None):
    """
    Total customers each forecast month = sheet's own forecasted new
    acquisitions (volume) + renewals of every past real cohort (via the
    live sBG retention curve). New acquisitions are priced at August 2026's
    real average price (fixed); renewals are priced at each cohort's own
    real locked-in recurring price (unchanged from the original design).

    cutoff_month_idx: if set, only use spells/renewals known strictly
    before this index (for backtesting against real historical months,
    where the sheet's own historical acquisitions -- not a forecast --
    should be used instead; see validate_final.py for that path).
    """
    if cutoff_month_idx is None:
        cutoff_month_idx = forecast_month_idx

    acquisitions_by_month_plan = defaultdict(lambda: defaultdict(list))
    for spell in spells:
        if month_index(spell["signup_month"]) >= cutoff_month_idx:
            continue
        acquisitions_by_month_plan[spell["plan"]][spell["signup_month"]].append(spell)

    total_orders = 0.0
    total_revenue = 0.0

    forecast_label = month_label(forecast_month_idx)
    sheet_acq_this_month = sheet_acquisitions.get(forecast_label, {})

    for plan, cycle_len, curve_key, sheet_key in [
        ("Monthly", 1, "monthly_curve", "monthly"),
        ("3-Month", 3, "threemonth_curve_cycles", "threemonth"),
    ]:
        curve = curves[curve_key]

        # renewals of every real past cohort
        for signup_month, cohort_spells in acquisitions_by_month_plan[plan].items():
            signup_idx = month_index(signup_month)
            months_since_signup = forecast_month_idx - signup_idx
            if months_since_signup <= 0:
                continue
            if months_since_signup % cycle_len != 0:
                continue
            units = months_since_signup // cycle_len
            retention = curve[units] if units < len(curve) else curve[-1]

            n = len(cohort_spells)
            still_active = n * retention
            avg_recurring_price = sum(
                resolve_recurring_price(s, price_history) or 0 for s in cohort_spells
            ) / n

            total_orders += still_active
            total_revenue += still_active * avg_recurring_price

        # new signups THIS forecast month -- volume from the sheet's own
        # forecast (Revenue Model!row9/row10), price fixed at August 2026's
        # real average
        n_new = sheet_acq_this_month.get(sheet_key, 0)
        price = AUGUST_AVG_PRICE[plan]
        total_orders += n_new
        total_revenue += n_new * price

    if total_orders == 0:
        return None
    return total_revenue / total_orders


if __name__ == "__main__":
    spells = load_cohorts("data/customer_cohorts.csv")
    with open("docs/curves.json") as f:
        curves = json.load(f)
    price_history = load_price_history("data/price_history.json")
    sheet_acquisitions = load_sheet_acquisition_forecast("data/sheet_acquisition_forecast.json")

    last_real_month_idx = month_index("2026-07")
    print("Forecast, next 6 months (using sheet's acquisition forecast + August's real price):")
    for i in range(1, 7):
        idx = last_real_month_idx + i
        forecast = forecast_aop(spells, idx, curves, price_history, sheet_acquisitions)
        label = month_label(idx)
        print(f"  {label}: £{forecast:.2f}" if forecast else f"  {label}: n/a")
