"""
LTV/CAC:LTV/Blended AOV formulas from Cohort Modelling, parameterized by a
`state` dict (see read_model_state.py) -- NOTHING here is hardcoded. Every
price, mix %, and baseline value is read live from the workbook each run.
"""


def monthly_revenue_per_customer(curve, t, state):
    return state["monthly_first_payment"] if t == 0 else curve[t] * state["monthly_fee"]


def threemonth_revenue_per_customer(curve_cycles, month, state):
    """curve_cycles indexed in renewal cycles (0,1,2,...). Non-renewal months = 0,
    matching the sheet's own behaviour (row417)."""
    if month == 0:
        return state["threemonth_month0_revenue"]
    if month % 3 != 0:
        return 0.0
    cycle = month // 3
    retention = curve_cycles[cycle] if cycle < len(curve_cycles) else curve_cycles[-1]
    return state["net_3month_price"] * retention


def blended_aov(curve_monthly, curve_3month_cycles, month, state):
    m = monthly_revenue_per_customer(curve_monthly, month, state)
    t3 = threemonth_revenue_per_customer(curve_3month_cycles, month, state)
    return state["mix_monthly"] * m + state["mix_3month"] * t3


def monthly_ltv_block(curve, state):
    """1st-year revenue-per-customer building block (Cohort Modelling!C36)."""
    return state["monthly_first_payment"] + state["monthly_fee"] * sum(curve[1:12])


def monthly_ltv_and_cac_ratio(curve, state):
    block = monthly_ltv_block(curve, state)
    ltv = block * state["gross_margin"]
    cac_ltv = ltv / state["cac_ltv_denom"]
    return ltv, cac_ltv


def threemonth_ltv_block(month9_retention, state):
    e27 = month9_retention * state["threemonth_fee"]  # row27 uses the LIST price (see README note)
    return (state["threemonth_month0_revenue"] + state["threemonth_month3_revenue"]
            + state["threemonth_month6_revenue"] + e27)


def threemonth_ltv_and_cac_ratio(month9_retention, state):
    block = threemonth_ltv_block(month9_retention, state)
    ltv = block * state["gross_margin"]
    cac_ltv = ltv / state["cac_ltv_denom"]
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
    workbooks. This pipeline can't recalculate the full workbook itself (see
    README) -- paste the new values into Excel, let it recalculate, save,
    then call this with the before/after files.
    """
    import openpyxl

    def get_row(path):
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb["Cash Flow"]
        rows = list(ws.iter_rows(values_only=True))
        return rows[0], rows[168]

    dates_old, old_row = get_row(old_xlsx_path)
    _, new_row = get_row(new_xlsx_path)

    print(f"\n{'Month':<12}{'Old Closing Balance':<22}{'New Closing Balance':<22}{'Delta'}")
    for i in range(1, min(len(old_row), len(new_row))):
        o, n = old_row[i], new_row[i]
        if not (isinstance(o, (int, float)) and isinstance(n, (int, float))):
            continue
        d = dates_old[i]
        label = d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d)
        print(f"{label:<12}{o:<22,.2f}{n:<22,.2f}{n-o:+,.2f}")
