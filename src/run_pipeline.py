"""
Run the whole pipeline: fit -> cross-validate -> derive sheet values ->
business impact -> narrative report.

    python3 src/run_pipeline.py

Output: outputs/report.md (human-readable) and outputs/sheet_updates.csv
(machine-readable, same as before).
"""
import csv
from sbg_model import load_series, clean_monotonic, build_obs, fit_sbg, predict_curve
from cross_validate import time_series_cv, summarize
import business_impact as bi

SHEET_MONTHLY = [1.0,0.7170083903,0.5566790632,0.4422522947,0.367300401,0.311674408,0.2591459491,
                 0.2487801112,0.2388289067,0.2292757504,0.2201047204,0.2113005316,0.2028485103,
                 0.1987915401,0.1948157093,0.1909193951,0.1871010072,0.1833589871,0.1796918074,
                 0.1760979712,0.1725760118,0.1691244916,0.1657420017,0.1624271617,0.1591786185]
SHEET_3MONTH_CYCLES = [1.0, 0.5817337683, 0.3246622985, 0.1952197031, 0.1800085743,
                       0.1694226301, 0.159459224, 0.150081746, 0.1426971238]
OLD_MONTHLY_TIERS = dict(r_7_12=0.04, r_13_24=0.02, r_post24=0.01)
OLD_3MONTH_TIERS = dict(r_9_12=0.03, r_13_24=0.02, r_post24=0.01)


def geometric_mean_rate(curve, t_start, t_end, months_per_period=1):
    ratio = curve[t_end] / curve[t_start]
    n_months = (t_end - t_start) * months_per_period
    return 1 - ratio ** (1 / n_months)


def flat_tier_curve(base0_6, r_7_12, r_13_24, r_post24, max_t):
    curve = list(base0_6)
    for t in range(len(base0_6), max_t + 1):
        r = r_7_12 if t <= 12 else (r_13_24 if t <= 24 else r_post24)
        curve.append(curve[-1] * (1 - r))
    return curve


def flat_tier_curve_3month(base_cycles_0_2, month9_val, r_9_12, r_12_24, r_post24, max_cycle):
    curve = list(base_cycles_0_2) + [month9_val]
    for cyc in range(4, max_cycle + 1):
        month = cyc * 3
        r = r_9_12 if month <= 12 else (r_12_24 if month <= 24 else r_post24)
        curve.append(curve[-1] * (1 - r) ** 3)
    return curve


def section(title):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


def run_monthly(report_rows):
    section("MONTHLY -- fitting")
    raw = load_series("data/monthly_counts.csv", "tenure_months")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    alpha, beta = fit_sbg(build_obs(cleaned))
    curve = predict_curve(alpha, beta, 48)
    print(f"alpha={alpha:.4f}, beta={beta:.4f}")

    section("MONTHLY -- cross-validation (raw curve)")
    cv_raw = summarize(
        time_series_cv(cleaned, predict_curve, SHEET_MONTHLY, n_splits=5,
                        min_train_frac=0.4, max_t=24),
        "Monthly raw sBG curve")

    r_7_12 = geometric_mean_rate(curve, 6, 12)
    r_13_24 = geometric_mean_rate(curve, 12, 24)
    r_post24 = geometric_mean_rate(curve, 24, 48)

    def new_tier_curve_fn(a, b, max_t):
        c = predict_curve(a, b, 12)
        rr712 = geometric_mean_rate(c, 6, 12) if max_t >= 12 else r_7_12
        return flat_tier_curve(SHEET_MONTHLY[0:7], rr712, r_13_24, r_post24, max_t)

    section("MONTHLY -- cross-validation (flat-tier numbers actually going in the sheet)")
    cv_tier = summarize(
        time_series_cv(cleaned, new_tier_curve_fn, SHEET_MONTHLY, n_splits=5,
                        min_train_frac=0.4, max_t=24),
        "Monthly flat-tier approximation")

    section("MONTHLY -- business impact")
    old_curve_full = flat_tier_curve(SHEET_MONTHLY[0:7], **OLD_MONTHLY_TIERS, max_t=24)
    new_curve_full = flat_tier_curve(SHEET_MONTHLY[0:7], r_7_12, r_13_24, r_post24, 24)
    old_ltv, old_cac_ltv = bi.monthly_ltv_and_cac_ratio(old_curve_full)
    new_ltv, new_cac_ltv = bi.monthly_ltv_and_cac_ratio(new_curve_full)
    impact_ltv = bi.compare(old_ltv, new_ltv, "Monthly 1st Yr LTV (Cohort Modelling!B43)", "£{:.2f}")
    impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, "Monthly CAC:LTV (Cohort Modelling!C43)", "{:.3f}x")

    confidence = "HIGH" if cv_tier and cv_tier["improved"] and cv_tier["n_points"] > 50 else "LOW"

    for cell, old, new, reason in [
        ("Model Assumptions!C32", 0.04, r_7_12, "Monthly M7-12 churn"),
        ("Cohort Modelling!B20", 0.04, r_7_12, "Monthly M7-12 churn (orphaned duplicate)"),
        ("Model Assumptions!C33", 0.02, r_13_24, "Monthly M13-24 churn"),
        ("Model Assumptions!C34", 0.01, r_post24, "Monthly post-M24 churn"),
    ]:
        report_rows.append(dict(
            cell=cell, old_value=f"{old:.4f}", new_value=f"{new:.4f}",
            finding=(
                f"{reason}: sheet assumed a flat {old*100:.1f}%/month churn rate here. "
                f"Fitting a shifted-Beta-Geometric model on {sum(len(s) for s in cleaned.values())} "
                f"cohort-month data points (alpha={alpha:.2f}, beta={beta:.2f}) and backing out "
                f"the equivalent flat rate for this window gives {new*100:.1f}%/month instead."
            ),
            why_changed=(
                f"Cross-validated with time-series CV ({cv_tier['n_folds']} folds, "
                f"{cv_tier['n_points']} held-out points): new rate MAE={cv_tier['mae_new']:.4f} "
                f"vs old rate MAE={cv_tier['mae_old']:.4f} "
                f"({'improvement' if cv_tier['improved'] else 'NOT an improvement'})."
            ) if cv_tier else "Cross-validation produced no usable folds -- treat with caution.",
            business_impact=(
                f"1st Yr LTV: {impact_ltv['old']:.2f} -> {impact_ltv['new']:.2f} "
                f"({impact_ltv['pct']:+.1f}%, {impact_ltv['direction']}); "
                f"CAC:LTV: {impact_cac['old']:.3f}x -> {impact_cac['new']:.3f}x "
                f"({impact_cac['direction']})"
            ),
            confidence=confidence,
        ))
    return alpha, beta, curve


def run_threemonth(report_rows):
    section("3-MONTH -- fitting")
    raw = load_series("data/threemonth_counts.csv", "tenure_cycles")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    alpha, beta = fit_sbg(build_obs(cleaned))
    curve = predict_curve(alpha, beta, 16)
    print(f"alpha={alpha:.4f}, beta={beta:.4f}")

    section("3-MONTH -- cross-validation (raw curve)")
    cv_raw = summarize(
        time_series_cv(cleaned, predict_curve, SHEET_3MONTH_CYCLES, n_splits=4,
                        min_train_frac=0.3, max_t=8),
        "3-Month raw sBG curve")

    month9_val = curve[3]
    r_9_12 = geometric_mean_rate(curve, 3, 4, months_per_period=3)
    r_13_24 = geometric_mean_rate(curve, 4, 8, months_per_period=3)
    r_post24 = geometric_mean_rate(curve, 8, 16, months_per_period=3)

    section("3-MONTH -- business impact")
    old_month9 = SHEET_3MONTH_CYCLES[3]
    old_ltv, old_cac_ltv = bi.threemonth_ltv_and_cac_ratio(old_month9)
    new_ltv, new_cac_ltv = bi.threemonth_ltv_and_cac_ratio(month9_val)
    impact_ltv = bi.compare(old_ltv, new_ltv, "3-Month 1st Yr LTV (Cohort Modelling!B50)", "£{:.2f}")
    impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, "3-Month CAC:LTV (Cohort Modelling!C50)", "{:.3f}x")

    n_points_raw = cv_raw["n_points"] if cv_raw else 0
    confidence = "LOW" if n_points_raw < 40 else "MEDIUM"

    report_rows.append(dict(
        cell="Cohort Modelling!K415 (I415, J415 flattened to =H415)",
        old_value=f"{old_month9:.4f} (via noisy compounded formula)",
        new_value=f"{month9_val:.6f}",
        finding=(
            f"Month-9 retention was computed by compounding two noisy calendar-month "
            f"ratios (month 7->8->9), even though months 7-8 aren't real renewal points "
            f"for a 3-month billing cycle -- see prior conversation for the exact -72%/+189% "
            f"swing that was being multiplied through. sBG (fit on cohort-level quarterly "
            f"checkpoints, alpha={alpha:.2f}, beta={beta:.2f}) predicts month 9 directly "
            f"without that contamination."
        ),
        why_changed=(
            f"Structural fix (formula -> static value), not a tier-fit -- see raw-curve CV above "
            f"({cv_raw['n_folds'] if cv_raw else 0} folds, {n_points_raw} held-out points, "
            f"MAE {cv_raw['mae_new']:.4f} vs sheet {cv_raw['mae_old']:.4f})." if cv_raw else "N/A"
        ),
        business_impact=(
            f"1st Yr LTV: {impact_ltv['old']:.2f} -> {impact_ltv['new']:.2f} "
            f"({impact_ltv['pct']:+.1f}%, {impact_ltv['direction']}); "
            f"CAC:LTV: {impact_cac['old']:.3f}x -> {impact_cac['new']:.3f}x "
            f"({impact_cac['direction']})"
        ),
        confidence="MEDIUM (isolated structural fix, less exposed to small-sample tier-fit noise)",
    ))

    for cell, old, new, reason in [
        ("Model Assumptions!C43", 0.03, r_9_12, "3-Month M7-12 churn (monthly-equiv.)"),
        ("Model Assumptions!C44", 0.02, r_13_24, "3-Month M13-24 churn (monthly-equiv.)"),
        ("Model Assumptions!C45", 0.01, r_post24, "3-Month post-M24 churn (monthly-equiv.)"),
    ]:
        report_rows.append(dict(
            cell=cell, old_value=f"{old:.4f}", new_value=f"{new:.4f}",
            finding=(
                f"{reason}: sheet assumed {old*100:.1f}%/month. sBG-implied monthly-equivalent "
                f"rate for this window is {new*100:.1f}%/month."
            ),
            why_changed=(
                f"Based on the same fit as month-9 above. Only {n_points_raw} held-out data "
                f"points exist this deep in the curve -- treat as directionally useful, "
                f"not fully validated."
            ),
            business_impact="Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.",
            confidence=confidence,
        ))
    return alpha, beta, curve


def write_report(report_rows):
    with open("outputs/report.md", "w") as f:
        f.write("# Retention Model Update -- Findings & Cell Changes\n\n")
        for row in report_rows:
            f.write(f"## `{row['cell']}`\n\n")
            f.write(f"- **Old value:** {row['old_value']}\n")
            f.write(f"- **New value:** {row['new_value']}\n")
            f.write(f"- **Finding:** {row['finding']}\n")
            f.write(f"- **Why changed (validation):** {row['why_changed']}\n")
            f.write(f"- **Business impact:** {row['business_impact']}\n")
            f.write(f"- **Confidence:** {row['confidence']}\n\n")

    with open("outputs/sheet_updates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
        w.writeheader()
        w.writerows(report_rows)

    print("\nWrote outputs/report.md and outputs/sheet_updates.csv")


if __name__ == "__main__":
    report_rows = []
    run_monthly(report_rows)
    run_threemonth(report_rows)
    write_report(report_rows)
