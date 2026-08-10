"""
Run the whole pipeline: read live model state -> fit -> cross-validate ->
derive sheet values -> business impact -> narrative report with justified
confidence ratings.

    python3 src/extract_data.py      # (re)build cohort CSVs from model.xlsx
    python3 src/run_pipeline.py      # everything else

Output: outputs/report.md and outputs/sheet_updates.csv
"""
import csv
import json
from sbg_model import load_series, clean_monotonic, build_obs, fit_sbg, predict_curve
from cross_validate import time_series_cv, summarize, confidence_rating
import business_impact as bi
from read_model_state import read_model_state


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


def run_monthly(report_rows, state):
    section("MONTHLY -- fitting")
    raw = load_series("data/monthly_counts.csv", "tenure_months")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    alpha, beta = fit_sbg(build_obs(cleaned))
    curve = predict_curve(alpha, beta, 48)
    print(f"alpha={alpha:.4f}, beta={beta:.4f}")

    current_curve = state["current_monthly_curve"]  # live-read, not hardcoded

    section("MONTHLY -- cross-validation (raw curve)")
    cv_raw = summarize(
        time_series_cv(cleaned, predict_curve, current_curve, n_splits=5,
                        min_train_frac=0.4, max_t=24),
        "Monthly raw sBG curve")

    r_7_12 = geometric_mean_rate(curve, 6, 12)
    r_13_24 = geometric_mean_rate(curve, 12, 24)
    r_post24 = geometric_mean_rate(curve, 24, 48)

    def new_tier_curve_fn(a, b, max_t):
        c = predict_curve(a, b, 12)
        rr712 = geometric_mean_rate(c, 6, 12) if max_t >= 12 else r_7_12
        return flat_tier_curve(current_curve[0:7], rr712, r_13_24, r_post24, max_t)

    section("MONTHLY -- cross-validation (flat-tier numbers actually going in the sheet)")
    cv_tier = summarize(
        time_series_cv(cleaned, new_tier_curve_fn, current_curve, n_splits=5,
                        min_train_frac=0.4, max_t=24),
        "Monthly flat-tier approximation")
    conf_label, conf_reason = confidence_rating(cv_tier)

    section("MONTHLY -- business impact")
    # "old" curve for business impact = the CURRENT live curve, extended using
    # whatever flat rate it's ACTUALLY using beyond month 24 (derived from the
    # curve itself, not assumed -- see read_model_state.py docstring)
    old_r_7_12 = geometric_mean_rate(current_curve, 6, 12)
    old_r_13_24 = geometric_mean_rate(current_curve, 12, 24) if len(current_curve) > 24 else old_r_7_12
    old_r_post24 = geometric_mean_rate(current_curve, 24, 48) if len(current_curve) > 48 else old_r_13_24
    old_curve_full = current_curve[:25] if len(current_curve) >= 25 else \
        flat_tier_curve(current_curve[0:7], old_r_7_12, old_r_13_24, old_r_13_24, 24)
    new_curve_full = flat_tier_curve(current_curve[0:7], r_7_12, r_13_24, r_post24, 24)

    old_ltv, old_cac_ltv = bi.monthly_ltv_and_cac_ratio(old_curve_full, state)
    new_ltv, new_cac_ltv = bi.monthly_ltv_and_cac_ratio(new_curve_full, state)
    impact_ltv = bi.compare(old_ltv, new_ltv, "Monthly 1st Yr LTV (Cohort Modelling!B43)", "£{:.2f}")
    impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, "Monthly CAC:LTV (Cohort Modelling!C43)", "{:.3f}x")

    for cell, old, new, reason, old_rate_for_display in [
        ("Model Assumptions!C32", None, r_7_12, "Monthly M7-12 churn", old_r_7_12),
        ("Cohort Modelling!B20", old_r_7_12, r_7_12, "Monthly M7-12 churn (the cell the live curve actually uses)", old_r_7_12),
        ("Model Assumptions!C33", None, r_13_24, "Monthly M13-24 churn", old_r_13_24),
        ("Model Assumptions!C34", None, r_post24, "Monthly post-M24 churn", old_r_post24),
    ]:
        old_display = f"{old:.4f}" if old is not None else "(read live from sheet -- see note)"
        report_rows.append(dict(
            cell=cell, old_value=old_display, new_value=f"{new:.4f}",
            finding=(
                f"{reason}: the live curve currently implies a {old_rate_for_display*100:.1f}%/month "
                f"rate here (derived from the curve's own actual decay in this window, read "
                f"directly from Cohort Modelling!row248 -- not from any single input cell, "
                f"since input cells for this can be unused/inconsistent). Fitting sBG on "
                f"{sum(len(s) for s in cleaned.values())} cohort-month data points "
                f"(alpha={alpha:.2f}, beta={beta:.2f}) gives {new*100:.1f}%/month instead."
            ),
            why_changed=conf_reason,
            business_impact=(
                f"1st Yr LTV: £{impact_ltv['old']:.2f} -> £{impact_ltv['new']:.2f} "
                f"({impact_ltv['pct']:+.1f}%, {impact_ltv['direction']}); "
                f"CAC:LTV: {impact_cac['old']:.3f}x -> {impact_cac['new']:.3f}x "
                f"({impact_cac['direction']})"
            ),
            confidence=conf_label,
        ))
    return alpha, beta, curve


def run_threemonth(report_rows, state):
    section("3-MONTH -- fitting")
    raw = load_series("data/threemonth_counts.csv", "tenure_cycles")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    alpha, beta = fit_sbg(build_obs(cleaned))
    curve = predict_curve(alpha, beta, 16)
    print(f"alpha={alpha:.4f}, beta={beta:.4f}")

    current_curve = state["current_3month_curve"]  # live-read, cycle-indexed

    section("3-MONTH -- cross-validation (raw curve)")
    cv_raw = summarize(
        time_series_cv(cleaned, predict_curve, current_curve, n_splits=4,
                        min_train_frac=0.3, max_t=8),
        "3-Month raw sBG curve")
    conf_label, conf_reason = confidence_rating(cv_raw)

    month9_val = curve[3]
    r_9_12 = geometric_mean_rate(curve, 3, 4, months_per_period=3)
    r_13_24 = geometric_mean_rate(curve, 4, 8, months_per_period=3)
    r_post24 = geometric_mean_rate(curve, 8, 16, months_per_period=3)

    section("3-MONTH -- business impact")
    old_month9 = current_curve[3] if len(current_curve) > 3 else current_curve[-1]
    old_ltv, old_cac_ltv = bi.threemonth_ltv_and_cac_ratio(old_month9, state)
    new_ltv, new_cac_ltv = bi.threemonth_ltv_and_cac_ratio(month9_val, state)
    impact_ltv = bi.compare(old_ltv, new_ltv, "3-Month 1st Yr LTV (Cohort Modelling!B50)", "£{:.2f}")
    impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, "3-Month CAC:LTV (Cohort Modelling!C50)", "{:.3f}x")

    report_rows.append(dict(
        cell="Cohort Modelling!K415 (I415, J415 flattened to =H415)",
        old_value=f"{old_month9:.4f} (via noisy compounded formula)",
        new_value=f"{month9_val:.6f}",
        finding=(
            f"Month-9 retention was computed by compounding noisy calendar-month ratios "
            f"for months 7-8 (non-renewal months for a 3-month billing cycle). sBG "
            f"(alpha={alpha:.2f}, beta={beta:.2f}, fit on the quarterly-checkpoint cohort "
            f"data) predicts month 9 directly without that contamination."
        ),
        why_changed=conf_reason,
        business_impact=(
            f"1st Yr LTV: £{impact_ltv['old']:.2f} -> £{impact_ltv['new']:.2f} "
            f"({impact_ltv['pct']:+.1f}%, {impact_ltv['direction']}); "
            f"CAC:LTV: {impact_cac['old']:.3f}x -> {impact_cac['new']:.3f}x "
            f"({impact_cac['direction']})"
        ),
        confidence=conf_label,
    ))

    n_points_raw = cv_raw["n_points"] if cv_raw else 0
    for cell, new, reason in [
        ("Model Assumptions!C43", r_9_12, "3-Month M7-12 churn (monthly-equiv.)"),
        ("Model Assumptions!C44", r_13_24, "3-Month M13-24 churn (monthly-equiv.)"),
        ("Model Assumptions!C45", r_post24, "3-Month post-M24 churn (monthly-equiv.)"),
    ]:
        report_rows.append(dict(
            cell=cell, old_value="(read live -- see note)", new_value=f"{new:.4f}",
            finding=(
                f"{reason}: derived from the same fit as month-9 above. sBG-implied "
                f"monthly-equivalent rate for this window is {new*100:.1f}%/month."
            ),
            why_changed=(
                conf_reason + f" This specific tier is deeper into the curve than what the "
                f"raw-curve CV above directly tested ({n_points_raw} held-out points total "
                f"across the whole 3-Month curve) -- treat as less certain than the month-9 fix."
            ),
            business_impact="Affects 2yr/3yr/4yr LTV (not 1st Yr LTV) -- not separately computed here.",
            confidence="LOW" if conf_label != "HIGH" else "MEDIUM",  # always one notch below the
            # raw-curve rating, since these tiers are further from validated data than month 9 is
        ))
    return alpha, beta, curve


def write_report(report_rows, monthly_curve, threemonth_curve, state):
    with open("outputs/report.md", "w") as f:
        f.write("# Retention Model Update -- Findings & Cell Changes\n\n")
        f.write("All assumptions below (prices, mix, CAC, current curves) were read live "
                "from `model.xlsx` at run time -- nothing is hardcoded in this pipeline.\n\n")

        f.write("## Current plan mix (unaffected by this update)\n\n")
        f.write(f"- Monthly: {state['mix_monthly']*100:.0f}%\n")
        f.write(f"- 3-Month: {state['mix_3month']*100:.0f}%\n")
        f.write(f"- 6-Month: {state['mix_6month']*100:.0f}%\n")
        f.write(f"- OTP: {state['mix_otp']*100:.0f}%\n\n")

        f.write("## Blended AOV impact\n\n")
        f.write("| Month | Old Blended AOV | New Blended AOV | Delta |\n|---|---|---|---|\n")
        for month in [0, 3, 6, 9, 12]:
            old_aov = bi.blended_aov(state["current_monthly_curve"], state["current_3month_curve"], month, state)
            new_aov = bi.blended_aov(monthly_curve, threemonth_curve, month, state)
            f.write(f"| {month} | £{old_aov:.2f} | £{new_aov:.2f} | £{new_aov-old_aov:+.2f} |\n")
        f.write("\n")

        f.write("## Closing Balance (Cash Flow!row169) -- NOT computed automatically\n\n")
        f.write("This pipeline can't recalculate the full workbook. Paste the values below "
                "into your live copy, let Excel recalculate, save as `model_after.xlsx` "
                "(keep the original as `model_before.xlsx`), then run:\n\n")
        f.write("```python\nfrom business_impact import diff_closing_balance\n"
                "diff_closing_balance('model_before.xlsx', 'model_after.xlsx')\n```\n\n")

        f.write("## Confidence rating key\n\n")
        f.write("- **HIGH**: beats the current numbers on held-out data, wins consistently "
                "across CV folds, plenty of held-out points, no fit instability\n")
        f.write("- **MEDIUM**: beats the current numbers, but on a smaller sample or less "
                "consistently across folds\n")
        f.write("- **LOW**: either doesn't beat the current numbers, or the fit showed "
                "signs of instability (hit the optimizer's bounds) in at least one fold\n\n")

        for row in report_rows:
            f.write(f"## `{row['cell']}`\n\n")
            f.write(f"- **Old value:** {row['old_value']}\n")
            f.write(f"- **New value:** {row['new_value']}\n")
            f.write(f"- **Finding:** {row['finding']}\n")
            f.write(f"- **Confidence: {row['confidence']}** -- {row['why_changed']}\n")
            f.write(f"- **Business impact:** {row['business_impact']}\n\n")

    with open("outputs/sheet_updates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
        w.writeheader()
        w.writerows(report_rows)

    print("\nWrote outputs/report.md and outputs/sheet_updates.csv")


if __name__ == "__main__":
    state = read_model_state("model.xlsx")
    with open("data/model_state.json", "w") as f:
        json.dump(state, f, indent=2)

    report_rows = []
    _, _, monthly_curve = run_monthly(report_rows, state)
    _, _, threemonth_curve = run_threemonth(report_rows, state)
    write_report(report_rows, monthly_curve, threemonth_curve, state)
