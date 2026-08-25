"""
Estimates the CURRENT active-subscriber mix (what fraction of active
subscribers are on Monthly vs 3-Month right now), using:

  1. Real monthly acquisition counts, extracted from Shopify order history
     (orders_clean.csv, first_order rows only)
  2. The already-validated sBG retention curves (same ones powering the AOV
     simulator, read from curves.json)

This is NOT a forecast -- it's a backward-looking calculation using two
already-trusted inputs, which is why it doesn't need its own confidence
rating the way the mix-TREND model did. We're not extrapolating anything
uncertain; we're asking "given what we know already happened, and what we
already validated about how long people stay, what does the active base
look like today."

Formula:
    active_subscribers(plan) = sum over every past cohort month m of
        [ acquisitions(plan, m) * retention_curve[plan](tenure at today) ]

    current_mix(plan) = active_subscribers(plan) / sum of all plans' active_subscribers

Usage:
    python3 src/estimate_current_mix.py
"""
import csv
import json
from collections import defaultdict
from datetime import date


def month_index(month_str):
    y, m = month_str.split("-")
    return int(y) * 12 + int(m)


def load_monthly_acquisitions(path):
    """Returns {plan: {month_str: count}}"""
    by_plan_month = defaultdict(lambda: defaultdict(int))
    for row in csv.DictReader(open(path)):
        if row["order_type"] != "first_order":
            continue
        month = row["date"][:7]
        by_plan_month[row["plan"]][month] += 1
    return by_plan_month


def load_curves(path):
    with open(path) as f:
        data = json.load(f)
    return data["monthly_curve"], data["threemonth_curve_cycles"]


def estimate_active(acquisitions_by_month, curve, today_idx, cycle_length_months=1):
    """
    acquisitions_by_month: {month_str: count}
    curve: list, index = tenure (in months for Monthly, in cycles for 3-Month)
    cycle_length_months: 1 for Monthly, 3 for 3-Month (converts calendar
        months of tenure into the curve's own indexing units)
    """
    total_active = 0.0
    for month_str, count in acquisitions_by_month.items():
        signup_idx = month_index(month_str)
        tenure_months = today_idx - signup_idx
        if tenure_months < 0:
            continue
        tenure_units = tenure_months // cycle_length_months
        retention = curve[tenure_units] if tenure_units < len(curve) else curve[-1]
        total_active += count * retention
    return total_active


if __name__ == "__main__":
    acquisitions = load_monthly_acquisitions("data/orders_clean.csv")
    monthly_curve, threemonth_curve = load_curves("docs/curves.json")

    today = date.today()
    today_idx = today.year * 12 + today.month

    active_monthly = estimate_active(acquisitions["Monthly"], monthly_curve, today_idx, cycle_length_months=1)
    active_3month = estimate_active(acquisitions["3-Month"], threemonth_curve, today_idx, cycle_length_months=3)

    total = active_monthly + active_3month
    mix_monthly = active_monthly / total
    mix_3month = active_3month / total

    print(f"As of {today.isoformat()}:")
    print(f"  Estimated active Monthly subscribers:  {active_monthly:,.0f}")
    print(f"  Estimated active 3-Month subscribers:  {active_3month:,.0f}")
    print(f"  Estimated current mix -> Monthly: {mix_monthly*100:.1f}%, 3-Month: {mix_3month*100:.1f}%")
    print()
    print(f"  Sheet's current assumption (Cohort Modelling!B8:B9): Monthly 30.0%, 3-Month 65.0%")
