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


def forecast_aop(spells, forecast_month_idx, curves, price_history, cutoff_month_idx=None):
    """
    cutoff_month_idx: if set, only use spells/renewals known strictly
    before this index (for backtesting). Defaults to forecast_month_idx
    (i.e. use everything known up to the forecast month itself).
    """
    if cutoff_month_idx is None:
        cutoff_month_idx = forecast_month_idx

    acquisitions_by_month_plan = defaultdict(lambda: defaultdict(list))
    for spell in spells:
        if month_index(spell["signup_month"]) >= cutoff_month_idx:
            continue
        acquisitions_by_month_plan[spell["plan"]][spell["signup_month"]].append(spell)

    all_known_months = [m for plans in acquisitions_by_month_plan.values() for m in plans]
    if not all_known_months:
        return None
    last_month = max(all_known_months, key=month_index)

    total_orders = 0.0
    total_revenue = 0.0

    for plan, cycle_len, curve_key in [("Monthly", 1, "monthly_curve"),
                                        ("3-Month", 3, "threemonth_curve_cycles")]:
        curve = curves[curve_key]

        for signup_month, cohort_spells in acquisitions_by_month_plan[plan].items():
            signup_idx = month_index(signup_month)
            months_since_signup = forecast_month_idx - signup_idx
            if months_since_signup <= 0:
                continue  # handled by the new-signup block below
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

        # this forecast month's own new signups -- held flat at last known month's volume/price
        new_cohort = acquisitions_by_month_plan[plan].get(last_month, [])
        if new_cohort:
            n_new = len(new_cohort)
            avg_first_paid = sum(s["first_order_paid"] for s in new_cohort) / n_new
            total_orders += n_new
            total_revenue += n_new * avg_first_paid

    if total_orders == 0:
        return None
    return total_revenue / total_orders


if __name__ == "__main__":
    spells = load_cohorts("data/customer_cohorts.csv")
    with open("docs/curves.json") as f:
        curves = json.load(f)
    price_history = load_price_history("data/price_history.json")

    # Forecast the next 6 months forward from the last real month
    last_real_month_idx = month_index("2026-07")
    print("Forecast, next 6 months (using ALL available data):")
    for i in range(1, 7):
        idx = last_real_month_idx + i
        forecast = forecast_aop(spells, idx, curves, price_history)
        y, m = idx // 12, idx % 12
        if m == 0:
            y -= 1
            m = 12
        label = f"{y}-{m:02d}"
        print(f"  {label}: £{forecast:.2f}" if forecast else f"  {label}: n/a")
