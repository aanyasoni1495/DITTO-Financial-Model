"""
Builds a real, subscriber-level table: for each customer (by email), their
signup month, plan, first-order price paid, and their own actual recurring
price -- read directly from THEIR OWN recurring orders, not approximated
from a plan-wide average.

Handles the rare re-subscription case (customer churns, comes back later,
treated as a new cohort each time) by splitting a customer's order history
at each 'first_order' event into separate "subscription spells."

Usage:
    python3 src/build_customer_cohorts.py
"""
import csv
from collections import defaultdict


def build_spells(orders_path):
    """
    Returns a list of dicts, one per subscription spell:
      email, plan, signup_month, first_order_paid, recurring_price
      (recurring_price = average of that spell's own real recurring orders,
      None if they never renewed even once -- i.e. we don't yet know their
      true recurring price, only their discounted first-order price)
    """
    by_email = defaultdict(list)
    with open(orders_path) as f:
        for row in csv.DictReader(f):
            by_email[row["email"]].append(row)

    spells = []
    for email, orders in by_email.items():
        orders.sort(key=lambda r: r["created_at"])

        current_spell = None
        for row in orders:
            if row["order_type"] == "first_order":
                if current_spell is not None:
                    spells.append(current_spell)
                current_spell = dict(
                    email=email, plan=row["plan"], signup_month=row["date"][:7],
                    first_order_paid=float(row["total_paid"] or 0),
                    recurring_prices=[],
                )
            elif row["order_type"] == "recurring" and current_spell is not None:
                if row["plan"] == current_spell["plan"]:
                    current_spell["recurring_prices"].append(float(row["list_price"] or 0))
        if current_spell is not None:
            spells.append(current_spell)

    for spell in spells:
        rp = spell.pop("recurring_prices")
        spell["recurring_price"] = sum(rp) / len(rp) if rp else None
        spell["n_renewals_observed"] = len(rp)

    return spells


if __name__ == "__main__":
    spells = build_spells("data/orders_clean.csv")
    print(f"Total subscription spells: {len(spells)}")

    with_renewal_data = [s for s in spells if s["recurring_price"] is not None]
    print(f"Spells with at least one observed renewal (real recurring price known): {len(with_renewal_data)}")
    print(f"Spells with NO renewal yet (too new, or churned before first renewal): {len(spells) - len(with_renewal_data)}")

    with open("data/customer_cohorts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["email", "plan", "signup_month", "first_order_paid",
                                           "recurring_price", "n_renewals_observed"])
        w.writeheader()
        w.writerows(spells)
    print("Wrote data/customer_cohorts.csv")
