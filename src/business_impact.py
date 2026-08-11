"""
Replicates the specific LTV/CAC:LTV formula chain from Cohort Modelling
(traced by hand from the actual workbook -- see cell references below) so we
can compute the business-metric impact of a curve change without needing a
full workbook recalculation (which is too memory-heavy to run reliably in an
automated pipeline).

If the underlying sheet's base assumptions change (price, CAC, gross margin,
plan mix), update the constants below to match -- these are pulled from
Cohort Modelling!B1:B12 and won't auto-update themselves.
"""

# Base assumptions (Cohort Modelling!B1:B12) -- update if the sheet's inputs change
CAC = 60.0                  # B2: Cost of Paying Sub Acquisition Y1
ORGANIC_MIX = 0.35          # B3: Organic Mix Y1
MONTHLY_FEE = 40.0          # B5: Monthly Subscription Fee
THREEMONTH_FEE = 100.0      # B6: 3-Month fee
GROSS_MARGIN = 0.75         # B12: Gross Profit

CAC_LTV_DENOM = CAC * (1 - ORGANIC_MIX)  # $B$2*(1-$B$3), used in every CAC:LTV formula

# Current plan mix (Cohort Modelling!B8:B11) -- NOT changed by anything in this
# pipeline. Retention changes affect the LTV of each plan; they don't change
# which mix of plans you're assumed to be acquiring.
MIX_MONTHLY = 0.30    # B8
MIX_3MONTH = 0.65     # B9
MIX_6MONTH = 0.00     # B10
MIX_OTP = 0.05        # B11 = 1-(B8+B9+B10)

# NOTE: the sheet computes 3-Month revenue-per-customer TWO different ways in
# two different places, and they disagree:
#   - Cohort Modelling!row27 (feeds "1st Yr LTV") uses THREEMONTH_FEE (100, list price)
#   - Cohort Modelling!row417 (feeds "Blended AOV" in APPENDIX CAC Payback Model,
#     and is what actually flows toward Cash Flow) uses NET_3MONTH_PRICE below (81)
# This is a pre-existing inconsistency in the sheet, not something introduced
# by the retention model. Blended AOV below uses the row417 (net-price) path
# since that's the one that actually reaches cash-flow-adjacent calculations.
NET_3MONTH_PRICE = 81.0  # Cohort Modelling!B418

# Parts of the 3-Month "1st Yr LTV" (Cohort Modelling!C37 = SUM(B27:E27)) that
# are NOT affected by anything we change (months 0, 3, 6 -- all live-linked to
# real appendix data, untouched). Only E27 (month 9) changes.
THREEMONTH_B27 = 70.0            # month 0
THREEMONTH_C27 = 47.12043523     # month 3
THREEMONTH_D27 = 32.46622985     # month 6
# E27 = (month-9 retention) * THREEMONTH_FEE -- this is what changes

# Monthly "1st Yr LTV" building block (Cohort Modelling!C36 = SUM(B249:M249))
# B249 (=B36, first-payment revenue) is unaffected; C249:M249 = curve[1..11]*MONTHLY_FEE
MONTHLY_B249 = MONTHLY_FEE * 0.7  # = B36


def monthly_revenue_per_customer(curve, t):
    """Cohort Modelling!row249 equivalent, month t."""
    return MONTHLY_B249 if t == 0 else curve[t] * MONTHLY_FEE


def threemonth_revenue_per_customer(curve_cycles, month):
    """Cohort Modelling!row417 equivalent (net-price path). curve_cycles is
    indexed in renewal cycles (0,1,2,3...); month must be a multiple of 3, or 0."""
    if month == 0:
        return THREEMONTH_B27  # first payment, unaffected by retention curve
    if month % 3 != 0:
        return 0.0  # non-renewal month, no revenue -- matches sheet behaviour
    cycle = month // 3
    retention = curve_cycles[cycle] if cycle < len(curve_cycles) else curve_cycles[-1]
    return NET_3MONTH_PRICE * retention


def blended_aov(curve_monthly, curve_3month_cycles, month):
    m = monthly_revenue_per_customer(curve_monthly, month)
    t3 = threemonth_revenue_per_customer(curve_3month_cycles, month)
    # 6-Month and OTP are unaffected by anything in this pipeline -- treat as
    # constant contribution (0 here since MIX_6MONTH=0 currently; OTP is a
    # one-off with no retention curve at all)
    return MIX_MONTHLY * m + MIX_3MONTH * t3


def monthly_ltv_block(curve):
    """C36 equivalent: 1st-year revenue-per-customer building block."""
    return MONTHLY_B249 + MONTHLY_FEE * sum(curve[1:12])


def monthly_ltv_and_cac_ratio(curve):
    block = monthly_ltv_block(curve)
    ltv = block * GROSS_MARGIN          # B43
    cac_ltv = ltv / CAC_LTV_DENOM       # C43
    return ltv, cac_ltv


def threemonth_ltv_block(month9_retention):
    e27 = month9_retention * THREEMONTH_FEE
    return THREEMONTH_B27 + THREEMONTH_C27 + THREEMONTH_D27 + e27


def threemonth_ltv_and_cac_ratio(month9_retention):
    block = threemonth_ltv_block(month9_retention)
    ltv = block * GROSS_MARGIN          # B50
    cac_ltv = ltv / CAC_LTV_DENOM       # C50
    return ltv, cac_ltv


def compare(old_val, new_val, label, fmt="{:.2f}", higher_is_better=True):
    delta = new_val - old_val
    pct = 100 * (new_val / old_val - 1) if old_val else float("nan")
    if abs(pct) < 0.5:
        direction = "~no change"
    elif (delta > 0) == higher_is_better:
        direction = "IMPROVES"
    else:
        direction = "WORSENS"
    print(f"  {label}: {fmt.format(old_val)} -> {fmt.format(new_val)} "
          f"({delta:+.2f}, {pct:+.1f}%) [{direction}]")
    return dict(label=label, old=old_val, new=new_val, delta=delta, pct=pct, direction=direction)


def diff_closing_balance(old_xlsx_path, new_xlsx_path):
    """
    Reads Cash Flow!row169 ('CLOSING BALANCE') from two ALREADY-RECALCULATED
    workbooks (e.g. before/after pasting the new retention numbers into Excel
    and letting Excel recalculate -- this pipeline can't recalculate the full
    workbook itself, see README). Returns a month-by-month diff.

    Usage (not run automatically by run_pipeline.py -- call manually once you
    have both files):
        from business_impact import diff_closing_balance
        diff_closing_balance("model_before.xlsx", "model_after.xlsx")
    """
    import openpyxl

    def get_row(path):
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb["Cash Flow"]
        rows = list(ws.iter_rows(values_only=True))
        dates = rows[0]
        closing = rows[168]  # row 169, 1-indexed -> index 168
        return dates, closing

    dates_old, old_row = get_row(old_xlsx_path)
    dates_new, new_row = get_row(new_xlsx_path)

    print(f"\n{'Month':<12}{'Old Closing Balance':<22}{'New Closing Balance':<22}{'Delta'}")
    for i in range(1, min(len(old_row), len(new_row))):
        o, n = old_row[i], new_row[i]
        if o is None and n is None:
            continue
        d = dates_old[i]
        label = d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d)
        if isinstance(o, (int, float)) and isinstance(n, (int, float)):
            print(f"{label:<12}{o:<22,.2f}{n:<22,.2f}{n-o:+,.2f}")
