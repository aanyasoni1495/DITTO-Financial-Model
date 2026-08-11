"""
Runs BOTH models (sBG and BdW) on BOTH plans (Monthly, 3-Month): fits, cross-
validates, derives sheet-ready cell values, computes business impact, and
generates a report showing each model's findings plus a side-by-side
comparison per plan with a recommendation.

    python3 src/extract_data.py      # (re)build cohort CSVs from model.xlsx
    python3 src/run_pipeline.py      # everything else

Output: outputs/report.md and outputs/sheet_updates.csv
"""
import csv
import json
from sbg_model import load_series, clean_monotonic, build_obs, fit_sbg, predict_curve
from bdw_model import fit_bdw, predict_curve_bdw
from cross_validate import time_series_cv, summarize, confidence_rating
import business_impact as bi
from read_model_state import read_model_state


MODELS = {
    "sBG": dict(fit_fn=fit_sbg, curve_fn=predict_curve, n_params=2),
    "BdW": dict(fit_fn=fit_bdw, curve_fn=predict_curve_bdw, n_params=3),
}


def bdw_bound_check(params):
    alpha, beta, c = params
    return (alpha > 500 or beta > 500 or alpha < 0.01 or beta < 0.01
            or c < 0.15 or c > 4.8)


BOUND_CHECKS = {"sBG": None, "BdW": bdw_bound_check}  # None -> cross_validate's default


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


def section(title):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


def fit_and_cv(model_name, cleaned, current_curve, n_splits, min_train_frac, max_t):
    spec = MODELS[model_name]
    params = spec["fit_fn"](build_obs(cleaned))
    full_curve = spec["curve_fn"](*params, max_t)

    cv_results = time_series_cv(
        cleaned, spec["curve_fn"], current_curve, n_splits=n_splits,
        min_train_frac=min_train_frac, max_t=max_t,
        fit_fn=spec["fit_fn"], bound_check=BOUND_CHECKS[model_name],
    )
    cv = summarize(cv_results, f"{model_name}")
    conf_label, conf_reason = confidence_rating(cv)
    return dict(model=model_name, params=params, curve=full_curve,
                cv=cv, confidence=conf_label, confidence_reason=conf_reason)


def run_plan_monthly(report_rows, state, comparisons):
    section("MONTHLY")
    raw = load_series("data/monthly_counts.csv", "tenure_months")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    current_curve = state["current_monthly_curve"]
    n_points = sum(len(s) for s in cleaned.values())

    results = {}
    for model_name in MODELS:
        print(f"\n--- {model_name} ---")
        results[model_name] = fit_and_cv(
            model_name, cleaned, current_curve, n_splits=5, min_train_frac=0.4, max_t=24)
        print(f"Full fit: {results[model_name]['params']}")

    sbg_mae = results["sBG"]["cv"]["mae_new"] if results["sBG"]["cv"] else None
    bdw_mae = results["BdW"]["cv"]["mae_new"] if results["BdW"]["cv"] else None
    if sbg_mae and bdw_mae:
        winner = "BdW" if bdw_mae < sbg_mae else "sBG"
        pct = 100 * abs(1 - bdw_mae / sbg_mae) if winner == "BdW" else 100 * abs(1 - sbg_mae / bdw_mae)
    else:
        winner, pct = "sBG", 0.0
    comparisons["Monthly"] = dict(
        sbg_mae=sbg_mae, bdw_mae=bdw_mae, winner=winner, pct=pct,
        sbg_conf=results["sBG"]["confidence"], bdw_conf=results["BdW"]["confidence"],
        n_points=n_points,
    )
    print(f"\nHead-to-head: sBG MAE={sbg_mae:.4f} ({results['sBG']['confidence']}), "
          f"BdW MAE={bdw_mae:.4f} ({results['BdW']['confidence']}) -> {winner} wins")

    old_r_7_12 = geometric_mean_rate(current_curve, 6, 12)
    old_r_13_24 = geometric_mean_rate(current_curve, 12, 24) if len(current_curve) > 24 else old_r_7_12
    old_r_post24 = geometric_mean_rate(current_curve, 24, 48) if len(current_curve) > 48 else old_r_13_24

    for model_name, res in results.items():
        spec = MODELS[model_name]
        curve = spec["curve_fn"](*res["params"], 48)  # extend past CV's max_t=24 for the post-24 tier
        r_7_12 = geometric_mean_rate(curve, 6, 12)
        r_13_24 = geometric_mean_rate(curve, 12, 24)
        r_post24 = geometric_mean_rate(curve, 24, 48)
        new_curve_full = flat_tier_curve(current_curve[0:7], r_7_12, r_13_24, r_post24, 24)
        old_curve_full = current_curve[:25] if len(current_curve) >= 25 else \
            flat_tier_curve(current_curve[0:7], old_r_7_12, old_r_13_24, old_r_post24, 24)
        old_ltv, old_cac_ltv = bi.monthly_ltv_and_cac_ratio(old_curve_full, state)
        new_ltv, new_cac_ltv = bi.monthly_ltv_and_cac_ratio(new_curve_full, state)
        impact_ltv = bi.compare(old_ltv, new_ltv, f"[{model_name}] Monthly 1st Yr LTV", "£{:.2f}")
        impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, f"[{model_name}] Monthly CAC:LTV", "{:.3f}x")
        recommended = " (RECOMMENDED)" if model_name == winner else " (not recommended -- see comparison)"

        for cell, old, new, tag in [
            ("Model Assumptions!C32", None, r_7_12, "M7-12 churn"),
            ("Cohort Modelling!B20", old_r_7_12, r_7_12, "M7-12 churn (cell the live curve actually uses)"),
            ("Model Assumptions!C33", None, r_13_24, "M13-24 churn"),
            ("Model Assumptions!C34", None, r_post24, "post-M24 churn"),
        ]:
            old_display = f"{old:.4f}" if old is not None else "(read live from sheet)"
            report_rows.append(dict(
                plan="Monthly", model=model_name + recommended, cell=cell,
                old_value=old_display, new_value=f"{new:.4f}",
                finding=f"Monthly {tag}: fit params {res['params']} on {n_points} real data points.",
                confidence=res["confidence"], confidence_reason=res["confidence_reason"],
                business_impact=(f"1st Yr LTV: £{impact_ltv['old']:.2f} -> £{impact_ltv['new']:.2f} "
                                  f"({impact_ltv['direction']}); CAC:LTV {impact_cac['direction']}"),
            ))
    return results


def run_plan_threemonth(report_rows, state, comparisons):
    section("3-MONTH")
    raw = load_series("data/threemonth_counts.csv", "tenure_cycles")
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}
    current_curve = state["current_3month_curve"]
    n_points = sum(len(s) for s in cleaned.values())

    results = {}
    for model_name in MODELS:
        print(f"\n--- {model_name} ---")
        results[model_name] = fit_and_cv(
            model_name, cleaned, current_curve, n_splits=4, min_train_frac=0.3, max_t=8)
        print(f"Full fit: {results[model_name]['params']}")

    sbg_mae = results["sBG"]["cv"]["mae_new"] if results["sBG"]["cv"] else None
    bdw_mae = results["BdW"]["cv"]["mae_new"] if results["BdW"]["cv"] else None
    if sbg_mae and bdw_mae:
        winner = "BdW" if bdw_mae < sbg_mae else "sBG"
        pct = 100 * abs(1 - bdw_mae / sbg_mae) if winner == "BdW" else 100 * abs(1 - sbg_mae / bdw_mae)
    else:
        winner, pct = "sBG", 0.0
    comparisons["3-Month"] = dict(
        sbg_mae=sbg_mae, bdw_mae=bdw_mae, winner=winner, pct=pct,
        sbg_conf=results["sBG"]["confidence"], bdw_conf=results["BdW"]["confidence"],
        n_points=n_points,
    )
    print(f"\nHead-to-head: sBG MAE={sbg_mae:.4f} ({results['sBG']['confidence']}), "
          f"BdW MAE={bdw_mae:.4f} ({results['BdW']['confidence']}) -> {winner} wins")

    old_month9 = current_curve[3] if len(current_curve) > 3 else current_curve[-1]

    for model_name, res in results.items():
        spec = MODELS[model_name]
        curve = spec["curve_fn"](*res["params"], 16)  # extend past CV's max_t=8
        month9_val = curve[3]
        r_9_12 = geometric_mean_rate(curve, 3, 4, months_per_period=3)
        r_13_24 = geometric_mean_rate(curve, 4, 8, months_per_period=3)
        r_post24 = geometric_mean_rate(curve, 8, 16, months_per_period=3)
        old_ltv, old_cac_ltv = bi.threemonth_ltv_and_cac_ratio(old_month9, state)
        new_ltv, new_cac_ltv = bi.threemonth_ltv_and_cac_ratio(month9_val, state)
        impact_ltv = bi.compare(old_ltv, new_ltv, f"[{model_name}] 3-Month 1st Yr LTV", "£{:.2f}")
        impact_cac = bi.compare(old_cac_ltv, new_cac_ltv, f"[{model_name}] 3-Month CAC:LTV", "{:.3f}x")
        recommended = " (RECOMMENDED)" if model_name == winner else " (not recommended -- see comparison)"

        report_rows.append(dict(
            plan="3-Month", model=model_name + recommended,
            cell="Cohort Modelling!K415 (I415, J415 flattened to =H415)",
            old_value=f"{old_month9:.4f} (via noisy compounded formula)",
            new_value=f"{month9_val:.6f}",
            finding=f"3-Month month-9 retention: fit params {res['params']} on {n_points} real data points.",
            confidence=res["confidence"], confidence_reason=res["confidence_reason"],
            business_impact=(f"1st Yr LTV: £{impact_ltv['old']:.2f} -> £{impact_ltv['new']:.2f} "
                              f"({impact_ltv['direction']}); CAC:LTV {impact_cac['direction']}"),
        ))
        for cell, new, tag in [
            ("Model Assumptions!C43", r_9_12, "M7-12 churn (monthly-equiv.)"),
            ("Model Assumptions!C44", r_13_24, "M13-24 churn (monthly-equiv.)"),
            ("Model Assumptions!C45", r_post24, "post-M24 churn (monthly-equiv.)"),
        ]:
            report_rows.append(dict(
                plan="3-Month", model=model_name + recommended, cell=cell,
                old_value="(read live)", new_value=f"{new:.4f}",
                finding=f"3-Month {tag}: derived from the same fit as month-9 above.",
                confidence=res["confidence"], confidence_reason=res["confidence_reason"],
                business_impact="Affects 2yr/3yr/4yr LTV, not 1st Yr LTV -- not separately computed.",
            ))
    return results


def write_report(report_rows, comparisons, state):
    with open("outputs/report.md", "w") as f:
        f.write("# Retention Model Update -- sBG vs BdW, Both Plans\n\n")
        f.write("All assumptions (prices, mix, CAC, current curves) were read live from "
                "`model.xlsx` at run time. Both models are fit and cross-validated for both "
                "plans; each plan's comparison section recommends whichever model actually "
                "wins on held-out accuracy for that plan -- they are not assumed to be the same.\n\n")

        f.write("## Current plan mix (unaffected by any model choice)\n\n")
        f.write(f"- Monthly: {state['mix_monthly']*100:.0f}%\n")
        f.write(f"- 3-Month: {state['mix_3month']*100:.0f}%\n")
        f.write(f"- 6-Month: {state['mix_6month']*100:.0f}%\n")
        f.write(f"- OTP: {state['mix_otp']*100:.0f}%\n\n")

        f.write("## Model comparison, side by side\n\n")
        f.write("| Plan | sBG MAE | sBG confidence | BdW MAE | BdW confidence | Winner | Margin |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for plan, c in comparisons.items():
            f.write(f"| {plan} | {c['sbg_mae']:.4f} | {c['sbg_conf']} | {c['bdw_mae']:.4f} | "
                    f"{c['bdw_conf']} | **{c['winner']}** | {c['pct']:.1f}% |\n")
        f.write("\n**Recommendation:** use each plan's winning model's cell values below "
                "(marked RECOMMENDED); ignore the other model's rows for actual sheet updates "
                "-- they're shown for transparency, not for use.\n\n")

        f.write("## Confidence rating key\n\n")
        f.write("- **HIGH**: beats current numbers on held-out data, wins a large majority of "
                "CV folds, plenty of held-out points, no fit instability\n")
        f.write("- **MEDIUM**: beats current numbers, but on a smaller sample or less consistently\n")
        f.write("- **LOW**: either doesn't beat current numbers, or the fit was unstable in at "
                "least one fold (a sign of insufficient data, common for BdW's extra parameter "
                "on the 3-Month plan specifically)\n\n")

        for row in report_rows:
            f.write(f"## [{row['plan']}] `{row['cell']}` -- {row['model']}\n\n")
            f.write(f"- **Old value:** {row['old_value']}\n")
            f.write(f"- **New value:** {row['new_value']}\n")
            f.write(f"- **Finding:** {row['finding']}\n")
            f.write(f"- **Confidence: {row['confidence']}** -- {row['confidence_reason']}\n")
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
    comparisons = {}
    run_plan_monthly(report_rows, state, comparisons)
    run_plan_threemonth(report_rows, state, comparisons)

    section("SIDE-BY-SIDE COMPARISON")
    for plan, c in comparisons.items():
        print(f"{plan}: sBG={c['sbg_mae']:.4f} ({c['sbg_conf']})  "
              f"BdW={c['bdw_mae']:.4f} ({c['bdw_conf']})  -> {c['winner']} wins by {c['pct']:.1f}%")

    write_report(report_rows, comparisons, state)
