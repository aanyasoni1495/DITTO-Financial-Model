import numpy as np
from sbg_model import (
    load_series, clean_monotonic, cohort_month_index,
    build_obs, fit_sbg, predict_curve,
)

# ---- current hand-tuned sheet curves (pulled from Cohort Modelling tab) ----
# Monthly: months 0-48, from row 247 ("2b. Monthly Curve")
SHEET_MONTHLY = [
    1.0, 0.7170083903, 0.5566790632, 0.4422522947, 0.367300401, 0.311674408,
    0.2591459491, 0.2487801112, 0.2388289067, 0.2292757504, 0.2201047204,
    0.2113005316, 0.2028485103, 0.1987915401, 0.1948157093, 0.1909193951,
    0.1871010072, 0.1833589871, 0.1796918074, 0.1760979712, 0.1725760118,
    0.1691244916, 0.1657420017, 0.1624271617, 0.1591786185, 0.1575868323,
    0.1560109639, 0.1544508543, 0.1529063458, 0.1513772823, 0.1498635095,
    0.1483648744, 0.1468812256, 0.1454124134, 0.1439582893, 0.1425187064,
    0.1410935193, 0.1396825841, 0.1382857583, 0.1369029007, 0.1355338717,
    0.134178533, 0.1328367476, 0.1315083802, 0.1301932963, 0.1288913634,
    0.1276024498, 0.1263264253, 0.125063161,
]
# 3-Month: quarterly checkpoints 0,3,6,...24 -> cycles 0-8, from row 25
SHEET_3MONTH = [
    1.0, 0.5817337683, 0.3246622985, 0.1952197031, 0.1800085743,
    0.1694226301, 0.159459224, 0.150081746, 0.1426971238,
]


def mae(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.mean(np.abs(a - b)))


def run_segment(name, csv_path, tenure_col, sheet_curve, cutoff_calendar, max_extrapolate):
    print(f"\n{'='*60}\n{name}\n{'='*60}")
    raw = load_series(csv_path, tenure_col)
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}

    # --- full fit (all data) ---
    obs_full = build_obs(cleaned)
    alpha, beta = fit_sbg(obs_full)
    print(f"Full-data fit: alpha={alpha:.4f}, beta={beta:.4f}")
    curve_full = predict_curve(alpha, beta, max_extrapolate)

    # --- walk-forward backtest ---
    obs_train = build_obs(cleaned, cutoff_calendar=cutoff_calendar)
    a_bt, b_bt = fit_sbg(obs_train)
    print(f"Backtest fit (data through {cutoff_calendar}): alpha={a_bt:.4f}, beta={b_bt:.4f}")

    held_out_actual, held_out_sbg, held_out_sheet = [], [], []
    for cohort, series in cleaned.items():
        base = cohort_month_index(cohort)
        n0 = series.get(0)
        if not n0:
            continue
        for t, survivors in series.items():
            if t == 0:
                continue
            calendar = base + t
            known_at_cutoff = calendar <= cutoff_calendar
            if known_at_cutoff:
                continue  # only score genuinely held-out (future-at-cutoff) points
            actual_frac = survivors / n0
            sbg_pred = predict_curve(a_bt, b_bt, t)[t]
            sheet_pred = sheet_curve[t] if t < len(sheet_curve) else sheet_curve[-1]
            held_out_actual.append(actual_frac)
            held_out_sbg.append(sbg_pred)
            held_out_sheet.append(sheet_pred)

    n_points = len(held_out_actual)
    print(f"Held-out (future-at-cutoff) points scored: {n_points}")
    if n_points:
        print(f"  MAE  sBG model   vs actual: {mae(held_out_sbg, held_out_actual):.4f}")
        print(f"  MAE  sheet curve vs actual: {mae(held_out_sheet, held_out_actual):.4f}")

    return dict(alpha=alpha, beta=beta, curve_full=curve_full,
                alpha_bt=a_bt, beta_bt=b_bt)


if __name__ == "__main__":
    monthly_res = run_segment(
        "MONTHLY PLAN", "data/monthly_counts.csv", "tenure_months",
        SHEET_MONTHLY, cutoff_calendar=2026 * 12 + 2, max_extrapolate=48,
    )
    three_res = run_segment(
        "3-MONTH PLAN", "data/threemonth_counts.csv", "tenure_cycles",
        SHEET_3MONTH, cutoff_calendar=2026 * 12 + 2, max_extrapolate=16,
    )

    print("\n\nFull-fit curves (first 13 periods):")
    print("Monthly sBG :", [round(x, 4) for x in monthly_res["curve_full"][:13]])
    print("Monthly sheet:", SHEET_MONTHLY[:13])
    print("3-Month sBG :", [round(x, 4) for x in three_res["curve_full"][:9]])
    print("3-Month sheet:", SHEET_3MONTH[:9])
