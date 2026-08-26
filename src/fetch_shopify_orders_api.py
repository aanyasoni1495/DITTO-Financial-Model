"""
Pulls recent orders directly from Shopify's Admin API (read_orders scope,
last 60 days) and merges them into the existing data/orders_clean.csv --
APPENDS new orders, never replaces history, since the API token's scope is
limited to a 60-day rolling window while orders_clean.csv already contains
the full history back to March 2025 (built once from manual CSV exports).

This is the automated replacement for manually exporting Shopify orders
each month -- run this, then build_customer_cohorts.py picks up the
refreshed orders_clean.csv exactly as before.

Requires two environment variables (set as GitHub Secrets in the workflow):
    SHOPIFY_ACCESS_TOKEN
    SHOPIFY_STORE_DOMAIN

Usage:
    python3 src/fetch_shopify_orders_api.py
"""
import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests

from extract_shopify_orders import parse_plan, parse_order_type, parse_price_test_tag

API_VERSION = "2026-07"
PAGE_SIZE = 250


def fetch_orders(store_domain, access_token, days_back=60):
    """Fetches orders from the last `days_back` days via Shopify's REST
    Admin API, handling pagination via the Link header (Shopify's REST API
    uses cursor-based pagination, not simple page numbers)."""
    since = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
    url = f"https://{store_domain}/admin/api/{API_VERSION}/orders.json"
    params = dict(status="any", created_at_min=since, limit=PAGE_SIZE)
    headers = {"X-Shopify-Access-Token": access_token}

    all_orders = []
    while url:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        all_orders.extend(data.get("orders", []))

        # Shopify uses Link headers for pagination -- extract the "next" URL
        link_header = resp.headers.get("Link", "")
        next_url = None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
        url = next_url
        params = {}  # subsequent requests use the full next_url, no extra params needed

        if url:
            time.sleep(0.5)  # basic rate-limit courtesy

    return all_orders


def shopify_order_to_row(order):
    """
    Converts one Shopify API order object into the same flat row shape
    extract_shopify_orders.py produces from a manual CSV export, so
    downstream scripts (build_customer_cohorts.py etc.) don't need to know
    or care which source the data came from.
    """
    tags = order.get("tags", "") or ""
    line_items = order.get("line_items", [])
    if not line_items:
        return None

    # A subscription order should have exactly one relevant line item for
    # our purposes; if there are several, use the first (matches how the
    # manual CSV export -- one row per line item -- was already filtered
    # down to subscription-relevant rows upstream).
    item = line_items[0]

    plan = parse_plan(tags)
    if plan is None:
        return None
    order_type = parse_order_type(tags)
    price_test = parse_price_test_tag(tags)

    email = order.get("email") or order.get("contact_email") or ""
    created_at = order.get("created_at", "")
    total_paid = order.get("current_total_price") or order.get("total_price") or "0"
    list_price = item.get("price", "0")

    discount_amount = 0.0
    for alloc in item.get("discount_allocations", []):
        try:
            discount_amount += float(alloc.get("amount", 0))
        except (TypeError, ValueError):
            pass

    discount_codes = [dc.get("code", "") for dc in order.get("discount_codes", [])]

    return dict(
        order_name=order.get("name", ""),
        email=email,
        created_at=created_at,
        date=created_at[:10] if created_at else "",
        plan=plan,
        order_type=order_type or "",
        list_price=list_price,
        total_paid=total_paid,
        discount_amount=discount_amount,
        discount_code=",".join(discount_codes),
        price_test_date=price_test["test_date"] if price_test else "",
        price_test_group=price_test["group"] if price_test else "",
        financial_status=order.get("financial_status", ""),
    )


def merge_into_existing(new_rows, existing_path="data/orders_clean.csv"):
    """Appends new_rows into the existing CSV, de-duplicating by order_name
    (Shopify order numbers are unique and stable) so re-running this
    doesn't create duplicate rows for orders already captured."""
    existing_rows = []
    existing_order_names = set()
    if os.path.exists(existing_path):
        with open(existing_path, newline="") as f:
            for row in csv.DictReader(f):
                existing_rows.append(row)
                existing_order_names.add(row["order_name"])

    added = 0
    for row in new_rows:
        if row["order_name"] in existing_order_names:
            continue
        existing_rows.append({k: str(v) for k, v in row.items()})
        existing_order_names.add(row["order_name"])
        added += 1

    existing_rows.sort(key=lambda r: r["created_at"])

    if not existing_rows:
        print("No rows to write -- nothing fetched and no existing file found.")
        return 0

    fieldnames = list(existing_rows[0].keys())
    with open(existing_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing_rows)

    print(f"Added {added} new orders. Total orders in {existing_path}: {len(existing_rows)}")
    return added


if __name__ == "__main__":
    store_domain = os.environ.get("SHOPIFY_STORE_DOMAIN")
    access_token = os.environ.get("SHOPIFY_ACCESS_TOKEN")

    if not store_domain or not access_token:
        print("ERROR: SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN must be set as "
              "environment variables (GitHub Secrets in the workflow).")
        sys.exit(1)

    print(f"Fetching orders from {store_domain} (last 60 days, per the read_orders scope)...")
    raw_orders = fetch_orders(store_domain, access_token, days_back=60)
    print(f"Fetched {len(raw_orders)} raw orders from the API.")

    converted = []
    skipped = 0
    for order in raw_orders:
        row = shopify_order_to_row(order)
        if row is None:
            skipped += 1
            continue
        converted.append(row)

    print(f"Converted {len(converted)} orders with an identifiable plan tag "
          f"({skipped} skipped -- no plan tag, likely non-subscription orders).")

    merge_into_existing(converted)
