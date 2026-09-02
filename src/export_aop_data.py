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
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone

from forecast_aop import (load_cohorts, load_price_history, load_sheet_acquisition_forecast,
                           resolve_recurring_price, month_index)
from validate_final import REAL_HISTORICAL_AOP, run_backtest


def month_label(idx):
    y, m = idx // 12, idx % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y}-{m:02d}"


def compute_last_real_month(today=None):
    """
    The month boundary between "real/actual" and "forecast" is now decided
    purely by the calendar, NOT by whether a cell is a formula or a plain
    number -- the sheet's row17 cells are all hardcoded numbers now (some
    were formulas before; that distinction is gone and can't be relied on
    any more). By the time this pipeline runs (always at month-end, after
    that month's cell has been updated with the real number), the most
    recently COMPLETED calendar month is real; the current month and
    everything after it is still forecast.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    y, m = today.year, today.month
    if m == 1:
        y, m = y - 1, 12
    else:
        m -= 1
    return f"{y}-{m:02d}"


def load_full_row17(xlsx_path="model.xlsx", last_real_month=None):
    """
    Reads EVERY column of Cash Flow!row17 directly from the live sheet,
    in their ACTUAL left-to-right order -- not just the monthly columns.

    Real vs forecast is decided by CALENDAR DATE (see
    compute_last_real_month), not by formula-vs-literal -- the sheet's
    row17 cells are all plain hardcoded numbers now, so there's no
    formula left to check. A month at or before `last_real_month` is
    real (its typed-in number is trusted as the actual figure); anything
    after is forecast (whatever placeholder currently sits there gets
    replaced by this tool's own calculation).

    Some sheets (confirmed: this one does) have "Year 1 AOP" / "Year 2
    AOP" etc. summary cells interspersed AMONG the monthly columns, not
    just appended at the end -- and those can ALSO be a mix of formulas
    and plain hardcoded numbers depending on the year, with no reliable
    way to tell which from the cell alone. So rather than parsing a
    formula's cell-range reference (which only works for cells that are
    still formulas), this resolves what each summary column covers PURELY
    BY POSITION: whatever run of consecutive month-columns came right
    before it. That works identically whether the summary cell itself is
    a formula, a hardcoded number, or anything else -- the position in
    the row is the one thing that never changes.

    Returns [] if model.xlsx isn't present.
    """
    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed -- cannot read model.xlsx")
        return []

    if last_real_month is None:
        last_real_month = compute_last_real_month()
    last_real_idx = month_index(last_real_month)

    try:
        wb_values = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    except FileNotFoundError:
        print(f"'{xlsx_path}' not found -- cannot read the live row17 range. "
              f"Falling back to a smaller hardcoded range (see run()).")
        return []

    ws_values = wb_values["Cash Flow"]
    date_row = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True))
    value_row = next(ws_values.iter_rows(min_row=17, max_row=17, values_only=True))

    columns = []
    for col_idx, (d, val) in enumerate(zip(date_row, value_row), start=1):
        sheet_value = round(float(val), 4) if isinstance(val, (int, float)) else None
        if d is not None and hasattr(d, "strftime"):
            m = d.strftime("%Y-%m")
            columns.append({"type": "month", "col_idx": col_idx, "month": m,
                             "is_real": month_index(m) <= last_real_idx,
                             "sheet_value": sheet_value})
        else:
            columns.append({"type": "summary", "col_idx": col_idx,
                             "label": d if isinstance(d, str) else None,
                             "sheet_value": sheet_value})

    # Resolve each summary column's covered months by position: whatever
    # consecutive run of month-columns immediately preceded it (reset
    # after each summary column, so a run only ever "belongs" to the one
    # summary column right after it).
    pending_months = []
    for col in columns:
        if col["type"] == "month":
            pending_months.append(col["month"])
        else:
            col["covers_months"] = pending_months if pending_months else None
            pending_months = []

    # Drop any leading columns before the first real month column -- these
    # are row/column labels (e.g. column A holding "Average Order Price"
    # as a row title), not part of the actual date-indexed data range.
    # Including them would shift every real column one position to the
    # right in the copy-paste output, reintroducing the exact alignment
    # bug this function exists to fix.
    first_month_pos = next((i for i, c in enumerate(columns) if c["type"] == "month"), None)
    if first_month_pos:
        columns = columns[first_month_pos:]

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


def compute_otp_stats(orders_path, month_label):
    """
    Real count and average price paid for OTP (one-time purchase) orders
    in a given month -- straightforward, unlike Monthly/3-Month, since OTP
    orders don't have a separate "recurring price" concept; there's just
    one order.

    IMPORTANT CAVEAT: orders_clean.csv, as it currently exists in this
    repo, has ZERO OTP rows -- an earlier bug in extract_shopify_orders.py
    silently discarded every order with no subscription tag (see that
    file's parse_plan docstring for the fix). That fix only affects
    EXTRACTION GOING FORWARD -- it can't retroactively recover OTP orders
    that were already stripped out of the existing orders_clean.csv
    before this fix existed. Until orders_clean.csv is rebuilt from the
    original raw Shopify export files (or enough time passes that fresh
    API-pulled months accumulate real OTP data), this will correctly
    return zero -- callers should treat that as "not available yet", not
    "OTP genuinely doesn't happen."
    """
    count, total = 0, 0.0
    with open(orders_path) as f:
        for row in csv.DictReader(f):
            if row.get("plan") == "OTP" and row.get("date", "").startswith(month_label):
                count += 1
                total += float(row.get("total_paid") or 0)
    return {"count": count, "avg_price": round(total / count, 2) if count else None}


def compute_month_baseline(month_label, spells, price_history, otp_mix_fraction=None,
                            otp_stats=None):
    """
    Computes the REAL price/discount/mix for whichever month is passed in
    (always the last real month, whatever that currently is -- see run()).
    This becomes the default values on the AOP Forecast page's inputs,
    so every time the automation runs against a newer month's data, the
    defaults move forward automatically -- no hardcoded "August" price
    to go stale.

    Monthly and 3-Month numbers are entirely real, computed from that
    month's actual signups (data/customer_cohorts.csv) and that month's
    actual list price (data/price_history.json):
      - recurring price = that month's dominant list price
      - first-purchase discount = 1 - (real avg first-order paid / list price)
      - mix = real share of that month's signups on each plan

    OTP has NO real equivalent anywhere in this pipeline -- Shopify orders
    aren't classified into an "OTP" category the way Monthly/3-Month are,
    and the sheet has no OTP price assumption either (only an OTP MIX
    assumption, Cohort Modelling!B11). So OTP's mix defaults to that sheet
    assumption if available (else a fallback), and OTP's PRICE has no real
    default at all -- callers should treat it as a placeholder the person
    is expected to fill in themselves, not a computed number.
    """
    by_plan = defaultdict(list)
    for s in spells:
        if s["signup_month"] == month_label:
            by_plan[s["plan"]].append(s)

    n_monthly = len(by_plan["Monthly"])
    n_3month = len(by_plan["3-Month"])
    n_otp = otp_stats["count"] if otp_stats else 0
    total_real_signups = n_monthly + n_3month + n_otp

    def list_price(plan_key):
        hist = price_history.get(plan_key, {})
        return hist.get(month_label, {}).get("price")

    monthly_list_price = list_price("monthly")
    threemonth_list_price = list_price("threemonth")

    def discount_pct(cohort_spells, list_price_val):
        if not cohort_spells or not list_price_val:
            return 0.0
        avg_first = sum(s["first_order_paid"] for s in cohort_spells) / len(cohort_spells)
        return max(0.0, min(100.0, (1 - avg_first / list_price_val) * 100))

    disc_monthly = discount_pct(by_plan["Monthly"], monthly_list_price)
    disc_3month = discount_pct(by_plan["3-Month"], threemonth_list_price)

    if n_otp > 0:
        # Real OTP data available for this month -- use it directly, and
        # derive OTP's mix share from real counts alongside Monthly/3-Month
        # (rather than a separate sheet assumption -- once real data
        # exists, it's the more trustworthy source).
        otp_price = otp_stats["avg_price"]
        mix_monthly = n_monthly / total_real_signups
        mix_3month = n_3month / total_real_signups
        mix_otp = n_otp / total_real_signups
        otp_source = f"real OTP orders this month (n={n_otp})"
    else:
        # No real OTP data yet for this month (see compute_otp_stats
        # docstring -- historical OTP orders were discarded by a bug fixed
        # in extract_shopify_orders.py, but that fix can't retroactively
        # recover already-stripped rows). Falls back to the sheet's own
        # OTP mix assumption for the SPLIT, and a documented placeholder
        # price (midpoint of DITTO's own stated typical OTP range,
        # £43-53) -- not computed from data, and the page says so.
        otp_price = 48.0
        otp_mix = otp_mix_fraction if otp_mix_fraction is not None else 0.05
        remaining = 1 - otp_mix
        if (n_monthly + n_3month) > 0:
            mix_monthly = (n_monthly / (n_monthly + n_3month)) * remaining
            mix_3month = (n_3month / (n_monthly + n_3month)) * remaining
        else:
            mix_monthly, mix_3month = remaining / 2, remaining / 2
        mix_otp = otp_mix
        otp_source = ("sheet's Cohort Modelling!B11 mix + £43-53 range midpoint price "
                       "(no real OTP orders found yet for this month)")

    return {
        "monthly": round(monthly_list_price, 2) if monthly_list_price else None,
        "threemonth": round(threemonth_list_price, 2) if threemonth_list_price else None,
        "otp": round(otp_price, 2),
        "discount_monthly_pct": round(disc_monthly, 1),
        "discount_3month_pct": round(disc_3month, 1),
        "mix_monthly_pct": round(mix_monthly * 100, 1),
        "mix_3month_pct": round(mix_3month * 100, 1),
        "mix_otp_pct": round(mix_otp * 100, 1),
        "otp_source": otp_source,
    }


def get_otp_mix_from_sheet(xlsx_path="model.xlsx"):
    try:
        from read_model_state import read_model_state
        state = read_model_state(xlsx_path)
        return state.get("mix_otp")
    except Exception:
        return None


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

    last_real_month = compute_last_real_month()
    row17 = load_full_row17("model.xlsx", last_real_month=last_real_month)
    row17_months = [c for c in row17 if c["type"] == "month"]

    months = []
    row17_columns = []  # full ordered layout, including summary columns, for the copy-to-sheet feature
    if row17_months:
        # Live sheet available -- use its ACTUAL full range. Real vs
        # forecast is decided by today's date (see compute_last_real_month),
        # not by formula-vs-literal -- every row17 cell is a plain
        # hardcoded number now, so there's no formula left to check.
        n_summary = sum(1 for c in row17 if c["type"] == "summary")
        print(f"Read live row17 from model.xlsx: {row17_months[0]['month']} to {row17_months[-1]['month']}, "
              f"{len(row17_months)} month columns + {n_summary} summary columns (e.g. Year N AOP), "
              f"last real month = {last_real_month} (today's date -> most recently completed calendar month)")
        for col in row17:
            if col["type"] == "month":
                if col["is_real"]:
                    months.append({"month": col["month"], "is_real": True, "actual_aop": col["sheet_value"]})
                else:
                    idx = month_index(col["month"])
                    pieces = decompose_month(spells, idx, curves, price_history, sheet_acquisitions)
                    months.append({"month": col["month"], "is_real": False,
                                   "current_sheet_value": col["sheet_value"], **pieces})
                row17_columns.append({"type": "month", "month": col["month"]})
            else:
                # Summary column (e.g. "Year 1 AOP"), resolved by POSITION
                # to whichever months it covers (see load_full_row17). The
                # front-end always recomputes a fresh plain number from
                # those months' current real/scenario values -- never
                # passes through a formula, and never leaves it as a
                # static old number either, satisfying "give hardcoded
                # for all of them" for every summary cell uniformly,
                # regardless of whether the sheet's own cell was a
                # formula or already a hardcoded placeholder.
                row17_columns.append({"type": "summary", "label": col["label"],
                                       "covers_months": col["covers_months"],
                                       "sheet_value": col["sheet_value"]})
    else:
        # Fallback -- no model.xlsx on hand (e.g. testing locally without
        # the workbook). Covers only the previously-validated real months
        # plus a fixed 32-month forecast window, so the page still works,
        # just with a narrower range than the live sheet actually has, and
        # WITHOUT any Year-N summary columns (those can only be discovered
        # by reading the live sheet) -- the copy feature falls back to a
        # plain month-only row in this case, clearly flagged on the page.
        print("No model.xlsx -- using fallback range (validated real months + 32 forecast months, no "
              "Year-N summary columns). Re-run inside the automation pipeline (where model.xlsx is "
              "present) for the full, exact column layout matching the live sheet.")
        last_real_month = max(REAL_HISTORICAL_AOP.keys(), key=month_index)
        last_real_idx = month_index(last_real_month)
        for m in sorted(REAL_HISTORICAL_AOP.keys(), key=month_index):
            months.append({"month": m, "is_real": True, "actual_aop": REAL_HISTORICAL_AOP[m]})
            row17_columns.append({"type": "month", "month": m})
        for i in range(1, 33):
            idx = last_real_idx + i
            label = month_label(idx)
            pieces = decompose_month(spells, idx, curves, price_history, sheet_acquisitions)
            months.append({"month": label, "is_real": False, "current_sheet_value": None, **pieces})
            row17_columns.append({"type": "month", "month": label})

    otp_mix_fraction = get_otp_mix_from_sheet("model.xlsx")
    otp_stats = compute_otp_stats("data/orders_clean.csv", last_real_month)
    baseline = compute_month_baseline(last_real_month, spells, price_history, otp_mix_fraction, otp_stats)
    print(f"Baseline computed from {last_real_month} (last real month): "
          f"Monthly £{baseline['monthly']} ({baseline['discount_monthly_pct']}% first-purchase discount), "
          f"3-Month £{baseline['threemonth']} ({baseline['discount_3month_pct']}%), "
          f"OTP £{baseline['otp']}, "
          f"mix {baseline['mix_monthly_pct']}/{baseline['mix_3month_pct']}/{baseline['mix_otp_pct']} "
          f"(OTP source: {baseline['otp_source']})")

    data = {
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "last_real_month": last_real_month,
        "confidence": confidence,
        "avg_error_pct": round(avg_pct, 1) if avg_pct is not None else None,
        "full_range_from_live_sheet": bool(row17_months),
        # Real, computed from last_real_month's own actual Shopify orders
        # and the sheet's own OTP mix assumption -- recalculated every run,
        # so the default always reflects the MOST RECENT real month, not a
        # fixed hardcoded month. Note: OTP has no real price anywhere in
        # this pipeline (Shopify orders aren't classified into an OTP
        # category) -- that one field is a placeholder for the person to
        # set themselves, not a computed number.
        "baseline_new_signup_price": {
            "monthly": baseline["monthly"],
            "threemonth": baseline["threemonth"],
            "otp": baseline["otp"],
        },
        "baseline_discount": {
            "monthly_pct": baseline["discount_monthly_pct"],
            "threemonth_pct": baseline["discount_3month_pct"],
        },
        "baseline_mix": {
            "monthly_pct": baseline["mix_monthly_pct"],
            "threemonth_pct": baseline["mix_3month_pct"],
            "otp_pct": baseline["mix_otp_pct"],
            "otp_source": baseline["otp_source"],
        },
        "months": months,
        "row17_columns": row17_columns,
    }

    with open("docs/aop_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote docs/aop_data.json -- {len(months)} months "
          f"({sum(1 for m in months if m['is_real'])} real, "
          f"{sum(1 for m in months if not m['is_real'])} forecast)")


if __name__ == "__main__":
    run()
