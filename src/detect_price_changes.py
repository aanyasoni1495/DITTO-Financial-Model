"""
Builds a month-by-month "price in effect" lookup per plan, from real
first-order list prices in the Shopify export.

Your actual pricing history turned out to be much more continuous than a
handful of one-off changes -- nearly every month shows a different dominant
price point for both plans, consistent with ongoing A/B price testing
(confirmed directly: the 'price_test_date'/'price_test_group' tags on
recent orders show sequential test escalations, e.g. 3-Month
89.94 -> 112.35 -> 118.90 across consecutive August 2026 tests).

Given that, "price in effect" for a given month is defined as the MODE
(most common) first-order list price that month -- this is a genuine,
data-derived number for every historical month, not an assumption.

Usage:
    python3 src/detect_price_changes.py
"""
import csv
import json
from collections import defaultdict, Counter


def load_monthly_dominant_price(path, plan):
    prices_by_month = defaultdict(Counter)
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["order_type"] != "first_order":
                continue
            if row["plan"] != plan:
                continue
            month = row["date"][:7]
            price = round(float(row["list_price"]), 2)
            prices_by_month[month][price] += 1

    result = {}
    for month, counter in sorted(prices_by_month.items()):
        total = sum(counter.values())
        dominant_price, dominant_count = counter.most_common(1)[0]
        result[month] = dict(
            price=dominant_price,
            share_at_dominant_price=round(dominant_count / total, 3),
            n_orders=total,
            n_distinct_prices=len(counter),
        )
    return result


def latest_price(monthly_prices):
    """The most recent month's dominant price -- used as 'today's price'
    when projecting forward, until told otherwise."""
    last_month = max(monthly_prices.keys())
    return monthly_prices[last_month]["price"], last_month


if __name__ == "__main__":
    monthly_m = load_monthly_dominant_price("data/orders_clean.csv", "Monthly")
    monthly_3 = load_monthly_dominant_price("data/orders_clean.csv", "3-Month")

    print("MONTHLY -- price in effect by month:")
    for month, info in monthly_m.items():
        flag = "" if info["share_at_dominant_price"] > 0.6 else "  <- price was genuinely mixed/testing this month"
        print(f"  {month}: £{info['price']:.2f} "
              f"({info['share_at_dominant_price']*100:.0f}% of {info['n_orders']} orders, "
              f"{info['n_distinct_prices']} distinct prices seen){flag}")

    print("\n3-MONTH -- price in effect by month:")
    for month, info in monthly_3.items():
        flag = "" if info["share_at_dominant_price"] > 0.6 else "  <- price was genuinely mixed/testing this month"
        print(f"  {month}: £{info['price']:.2f} "
              f"({info['share_at_dominant_price']*100:.0f}% of {info['n_orders']} orders, "
              f"{info['n_distinct_prices']} distinct prices seen){flag}")

    p_m, m_month = latest_price(monthly_m)
    p_3, m3_month = latest_price(monthly_3)
    print(f"\nCurrent price (most recent month): Monthly £{p_m:.2f} (as of {m_month}), "
          f"3-Month £{p_3:.2f} (as of {m3_month})")

    with open("data/price_history.json", "w") as f:
        json.dump(dict(monthly=monthly_m, threemonth=monthly_3), f, indent=2)
    print("\nWrote data/price_history.json")
