"""
Generates the exact list of cell changes needed to update the DITTO Financial
Model with the latest sBG fit -- run this, read the table, paste the values.

This does NOT write to the xlsx. It only tells you what to change and where.
(There's a separate apply_updates.py if you want it written in automatically.)

Usage:
    python3 src/generate_sheet_updates.py
"""
import csv
from sbg_model import load_series, clean_monotonic, build_obs, fit_sbg, predict_curve


def geometric_mean_rate(curve, t_start, t_end, months_per_period=1):
    """Flat monthly churn rate that reproduces curve[t_end]/curve[t_start] if
    applied every month from t_start to t_end. t_start/t_end are in the
    curve's own units (months, or cycles if months_per_period=3)."""
    ratio = curve[t_end] / curve[t_start]
    n_months = (t_end - t_start) * months_per_period
    return 1 - ratio ** (1 / n_months)


def main():
    rows = []

    # ---- Monthly ----
    raw = load_series("data/monthly_counts.csv", "tenure_months")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    alpha, beta = fit_sbg(build_obs(cleaned))
    curve = predict_curve(alpha, beta, 48)

    r_7_12 = geometric_mean_rate(curve, 6, 12)
    r_13_24 = geometric_mean_rate(curve, 12, 24)
    r_post24 = geometric_mean_rate(curve, 24, 48)

    rows.append(["Model Assumptions", "C32", "0.03", f"{r_7_12:.4f}",
                 "Monthly M7-12 churn, sBG-implied"])
    rows.append(["Cohort Modelling", "B20", "0.04", f"{r_7_12:.4f}",
                 "Monthly M7-12 churn (orphaned duplicate of Model Assumptions!C32 -- also fix here)"])
    rows.append(["Model Assumptions", "C33", "0.02", f"{r_13_24:.4f}",
                 "Monthly M13-24 churn, sBG-implied"])
    rows.append(["Model Assumptions", "C34", "0.01", f"{r_post24:.4f}",
                 "Monthly post-M24 churn, sBG-implied"])

    # ---- 3-Month ----
    raw3 = load_series("data/threemonth_counts.csv", "tenure_cycles")
    cleaned3 = {c: clean_monotonic(s) for c, s in raw3.items()}
    a3, b3 = fit_sbg(build_obs(cleaned3))
    curve3 = predict_curve(a3, b3, 16)  # cycles, 1 cycle = 3 months

    # month-9 fix (kills the noisy month7/8 contamination) -- cycle 3
    rows.append(["Cohort Modelling", "K415", "(formula)", f"{curve3[3]:.6f}",
                 "Month-9 retention, sBG cycle-3 value (replaces noisy compounded formula)"])

    # flat tiers, expressed as MONTHLY rates (since the sheet applies these
    # month-by-month even for the 3-month plan) -- geometric mean converted
    # from the model's per-cycle (3-month) rate
    r3_7_12 = geometric_mean_rate(curve3, 3, 4, months_per_period=3)     # cycle3->4 = month9->12
    r3_13_24 = geometric_mean_rate(curve3, 4, 8, months_per_period=3)    # cycle4->8 = month12->24
    r3_post24 = geometric_mean_rate(curve3, 8, 16, months_per_period=3)  # cycle8->16 = month24->48

    rows.append(["Model Assumptions", "C43", "0.03", f"{r3_7_12:.4f}",
                 "3-Month M7-12 churn (monthly-equivalent), sBG-implied"])
    rows.append(["Model Assumptions", "C44", "0.02", f"{r3_13_24:.4f}",
                 "3-Month M13-24 churn (monthly-equivalent), sBG-implied"])
    rows.append(["Model Assumptions", "C45", "0.01", f"{r3_post24:.4f}",
                 "3-Month post-M24 churn (monthly-equivalent), sBG-implied"])

    print(f"Monthly fit: alpha={alpha:.4f}, beta={beta:.4f}")
    print(f"3-Month fit: alpha={a3:.4f}, beta={b3:.4f}\n")

    print(f"{'Sheet':<20}{'Cell':<8}{'Old':<12}{'New':<10}Reason")
    print("-" * 100)
    for r in rows:
        print(f"{r[0]:<20}{r[1]:<8}{r[2]:<12}{r[3]:<10}{r[4]}")

    with open("outputs/sheet_updates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "cell", "old_value", "new_value", "reason"])
        w.writerows(rows)
    print("\nSaved to outputs/sheet_updates.csv")


if __name__ == "__main__":
    main()
