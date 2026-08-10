"""
Reads every assumption and the CURRENT live curve directly out of model.xlsx,
every time this runs. Nothing about the sheet's current state is hardcoded
anywhere else in this pipeline -- that's a deliberate fix after a mix-up
between Model Assumptions!C32 (unused, 0.03) and Cohort Modelling!B20
(the cell the live curve actually uses, 0.04) made it into an earlier report.

Rather than trying to guess which of several possibly-inconsistent input
cells actually drives the curve, this reads the CURVE ITSELF (the computed
output, e.g. Cohort Modelling!row248) directly -- that's the one thing that
can't be ambiguous, since it's what the sheet is actually using today,
regardless of which upstream cell fed it.

Usage:
    from read_model_state import read_model_state
    state = read_model_state("model.xlsx")
    state["current_monthly_curve"]   # list, index = months since signup
    state["current_3month_curve"]    # list, index = renewal CYCLES (x3 months)
    state["cac"], state["gross_margin"], etc.
"""
import json
import openpyxl


def read_model_state(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    cm = wb["Cohort Modelling"]
    cm_rows = list(cm.iter_rows(values_only=True))

    def cell(row_idx, col_idx):  # 1-indexed, like Excel
        row = cm_rows[row_idx - 1]
        return row[col_idx - 1] if col_idx - 1 < len(row) else None

    state = {}

    # --- base assumptions (Cohort Modelling!B1:B12) ---
    state["cac"] = cell(2, 2)
    state["organic_mix"] = cell(3, 2)
    state["monthly_fee"] = cell(5, 2)
    state["threemonth_fee"] = cell(6, 2)
    state["sixmonth_fee"] = cell(7, 2)
    state["mix_monthly"] = cell(8, 2)
    state["mix_3month"] = cell(9, 2)
    state["mix_6month"] = cell(10, 2)
    state["mix_otp"] = cell(11, 2)
    state["gross_margin"] = cell(12, 2)
    state["cac_ltv_denom"] = state["cac"] * (1 - state["organic_mix"])

    # --- the ACTUAL live curves, read as computed output (not reconstructed
    # from input assumptions, which may be inconsistent/unused -- see docstring) ---
    monthly_curve = []
    col = 2  # column B = month 0
    while True:
        v = cell(248, col)
        if v is None:
            break
        monthly_curve.append(v)
        col += 1
    state["current_monthly_curve"] = monthly_curve

    threemonth_curve_monthly_granularity = []
    col = 2
    while True:
        v = cell(415, col)
        if v is None:
            break
        threemonth_curve_monthly_granularity.append(v)
        col += 1
    # resample at quarterly checkpoints (0,3,6,9,...) -> cycle-indexed
    state["current_3month_curve"] = threemonth_curve_monthly_granularity[0::3]
    state["current_3month_curve_monthly_granularity"] = threemonth_curve_monthly_granularity

    # --- 3-Month net price used by row417 (Blended AOV / cash-flow-facing path) ---
    state["net_3month_price"] = cell(418, 2)

    # --- baseline revenue-per-customer building blocks, unaffected by retention curve ---
    state["monthly_first_payment"] = cell(249, 2)  # B249
    state["threemonth_month0_revenue"] = cell(27, 2)   # B27 = month 0
    state["threemonth_month3_revenue"] = cell(27, 3)   # C27 = month 3
    state["threemonth_month6_revenue"] = cell(27, 4)   # D27 = month 6
    state["threemonth_month9_revenue_CURRENT"] = cell(27, 5)  # E27 = month 9, this is what our fix changes

    # --- flag which specific cells actually feed the live curve, so future
    # runs don't need to re-derive this by hand ---
    state["notes"] = [
        "current_monthly_curve read from Cohort Modelling!row248 (computed output).",
        "current_3month_curve read from Cohort Modelling!row415, resampled every 3rd "
        "month (computed output, monthly granularity underneath).",
        "These are read as OUTPUTS, not reconstructed from input assumption cells, "
        "specifically because input cells can be unused/inconsistent (e.g. Model "
        "Assumptions!C32 vs Cohort Modelling!B20 -- see README).",
    ]
    return state


if __name__ == "__main__":
    state = read_model_state("model.xlsx")
    with open("data/model_state.json", "w") as f:
        json.dump(state, f, indent=2)
    print("Wrote data/model_state.json")
    print(f"CAC={state['cac']}, gross_margin={state['gross_margin']}, "
          f"mix=({state['mix_monthly']}, {state['mix_3month']}, {state['mix_6month']}, {state['mix_otp']})")
    print(f"Monthly curve length: {len(state['current_monthly_curve'])} months")
    print(f"Monthly curve months 0-12: {[round(x,4) for x in state['current_monthly_curve'][:13]]}")
    print(f"3-Month curve (cycles): {[round(x,4) for x in state['current_3month_curve'][:9]]}")
