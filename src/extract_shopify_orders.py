"""
Extracts order-level data from the raw Shopify order exports into a clean,
one-row-per-order CSV: date, plan, list price, price actually paid, and
whether it's a first order or a recurring renewal.

Plan type comes from the 'Tags' field (set by Appstle, your subscription
app) -- NOT from 'Lineitem name', since the product got renamed at least
twice during the export's history ('Cycle Supplement' -> 'Premenstrual
Daily' etc.) while Tags consistently records 'Monthly' / '3-Month' /
'6-Month' regardless of the product name at the time.

Usage:
    python3 src/extract_shopify_orders.py data/orders_export_*.csv
"""
import csv
import re
import sys
from datetime import datetime

PLAN_TAGS = {
    "Monthly": "Monthly",
    "Month": "Monthly",       # same plan, alternate tag seen in the data
    "3-Month": "3-Month",
    "Quarterly": "3-Month",   # same plan, alternate tag seen in the data
    "6-Month": "6-Month",
    "Annual": "Annual",       # newly discovered -- only 19 orders total, flagged separately
}


def parse_plan(tags):
    """
    Monthly/3-Month/6-Month/Annual come from Appstle's subscription tags.
    Any order with NO subscription tag at all is a one-time purchase
    (OTP) -- confirmed directly: DITTO's own business rule is that every
    order not tagged into a subscription plan IS an OTP order, not a
    garbage/unclassifiable row. Earlier versions of this function
    returned None here and the caller silently dropped these rows
    entirely (see the old "skipped_no_plan" counter) -- that was wrong;
    it was quietly discarding every real OTP purchase instead of
    counting them. Fixed so OTP orders are now kept and classified.
    """
    if not tags:
        return "OTP"
    tag_list = [t.strip() for t in tags.split(",")]
    for raw_tag, canonical in PLAN_TAGS.items():
        if raw_tag in tag_list:
            return canonical
    return "OTP"


def parse_order_type(tags):
    if not tags:
        return None
    if "Subscription First Order" in tags or "First order" in tags:
        return "first_order"
    if "Subscription Recurring Order" in tags or "recurring_order" in tags:
        return "recurring"
    return None


def parse_price_test_tag(tags):
    """Looks for A/B price test tags like '140826-price-test-recurring' or
    'ig-070826-price-ctrl-50off' -- these carry a date (DDMMYY) and whether
    the order was in the test or control group. Returns None if no such tag."""
    if not tags:
        return None
    m = re.search(r"(?:ig-)?(\d{6})-price-(test|ctrl)", tags)
    if not m:
        return None
    date_str, group = m.groups()
    try:
        dt = datetime.strptime(date_str, "%d%m%y").date().isoformat()
    except ValueError:
        dt = None
    return dict(test_date=dt, group=group)


def extract(paths, out_path):
    rows_out = []
    skipped_no_plan = 0
    skipped_no_date = 0

    for path in paths:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                created = row.get("Created at")
                if not created:
                    skipped_no_date += 1
                    continue

                plan = parse_plan(row.get("Tags", ""))
                if plan is None:
                    skipped_no_plan += 1
                    continue

                order_type = parse_order_type(row.get("Tags", ""))
                price_test = parse_price_test_tag(row.get("Tags", ""))

                try:
                    list_price = float(row.get("Lineitem price") or 0)
                except ValueError:
                    list_price = None
                try:
                    paid = float(row.get("Total") or 0)
                except ValueError:
                    paid = None
                try:
                    discount = float(row.get("Discount Amount") or 0)
                except ValueError:
                    discount = 0.0

                rows_out.append(dict(
                    order_name=row.get("Name"),
                    email=row.get("Email", ""),
                    created_at=created,
                    date=created[:10],
                    plan=plan,
                    order_type=order_type or "",
                    list_price=list_price,
                    total_paid=paid,
                    discount_amount=discount,
                    discount_code=row.get("Discount Code", ""),
                    price_test_date=price_test["test_date"] if price_test else "",
                    price_test_group=price_test["group"] if price_test else "",
                    financial_status=row.get("Financial Status", ""),
                ))

    rows_out.sort(key=lambda r: r["created_at"])

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} orders to {out_path}")
    print(f"Skipped {skipped_no_plan} rows with no identifiable plan tag "
          f"(likely non-subscription line items, e.g. one-off add-ons)")
    print(f"Skipped {skipped_no_date} rows with no created-at date")

    from collections import Counter
    plan_counts = Counter(r["plan"] for r in rows_out)
    print("\nBy plan:")
    for plan, count in plan_counts.most_common():
        print(f"  {plan}: {count}")


if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        print("Usage: python3 extract_shopify_orders.py <csv files...>")
        sys.exit(1)
    extract(paths, "data/orders_clean.csv")
