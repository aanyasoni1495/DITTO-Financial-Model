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
