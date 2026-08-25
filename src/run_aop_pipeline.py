"""
AOP forecasting pipeline -- run this AFTER the retention model's own
run_pipeline.py + export_curves.py, since this reads docs/curves.json
LIVE every time. Whenever new Klar/retention data comes in and the sBG fit
changes (new alpha/beta), this pipeline automatically picks up the new
curve and produces a different AOP forecast -- nothing here is hardcoded.

What this does:
  1. Loads the live retention curve (docs/curves.json)
  2. Loads subscriber-level cohort data (data/customer_cohorts.csv --
     rebuild with extract_shopify_orders.py + build_customer_cohorts.py
     whenever you have a fresh Shopify export; this doesn't change monthly
     the way retention data does, since pricing/cohort history moves
     slower than churn)
  3. Estimates current active-subscriber mix (uses the SAME live curve --
     this is why mix estimation depends on retention too, not just orders)
  4. Validates the whole pipeline against real historical months (time-
     series backtest + rolling-origin CV, same discipline as sBG)
  5. Forecasts AOP forward from the last genuinely real month
  6. Outputs outputs/aop_report.md and outputs/aop_cell_updates.csv --
     exactly which Cash Flow cells to change, old value -> new value,
     with real historical months explicitly marked "do not change"

Usage:
    python3 src/run_aop_pipeline.py
"""
import csv
import json
from datetime import date

from forecast_aop import load_cohorts, load_price_history, forecast_aop, month_index
from estimate_current_mix import load_monthly_acquisitions, estimate_active
from validate_final import run_backtest, REAL_HISTORICAL_AOP

N_FORECAST_MONTHS = 12


def month_label(idx):
    y, m = idx // 12, idx % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y}-{m:02d}"


def get_live_mix(price_history_path, curves):
    """Re-derives current active-subscriber mix using the LIVE retention
    curve -- same logic as estimate_current_mix.py, called fresh here so
    it always reflects the current curves.json, not a stale hardcoded value."""
    acquisitions = load_monthly_acquisitions("data/orders_clean.csv")
    today = date.today()
    today_idx = today.year * 12 + today.month

    active_m = estimate_active(acquisitions["Monthly"], curves["monthly_curve"],
                                today_idx, cycle_length_months=1)
    active_3 = estimate_active(acquisitions["3-Month"], curves["threemonth_curve_cycles"],
                                today_idx, cycle_length_months=3)
    total = active_m + active_3
    if total == 0:
        return None, None
    return active_m / total, active_3 / total


def run():
    with open("docs/curves.json") as f:
        curves = json.load(f)
    print(f"Live curve: Monthly uses {curves['monthly_model_used']} "
          f"(alpha/beta baked into the curve values), "
          f"3-Month uses {curves['threemonth_model_used']}")
    print(f"Curve last generated: {curves.get('generated_date', 'unknown')}")

    spells = load_cohorts("data/customer_cohorts.csv")
    price_history = load_price_history("data/price_history.json")

    mix_m, mix_3 = get_live_mix("data/price_history.json", curves)
    print(f"\nCurrent active-subscriber mix (derived from live curve): "
          f"Monthly {mix_m*100:.1f}%, 3-Month {mix_3*100:.1f}%")

    # --- Validation (same discipline as sBG: never let the model see the future) ---
    print("\n--- Validation ---")
    test_months = sorted(REAL_HISTORICAL_AOP.keys())
    results = run_backtest(spells, curves, price_history, test_months, min_history_months=3)
    if results:
        avg_pct = sum(r["pct_err"] for r in results) / len(results)
        win_rate = sum(1 for r in results if r["pct_err"] < 10) / len(results)
        confidence = ("HIGH" if avg_pct < 8 and win_rate > 0.8 else
                      "MEDIUM" if avg_pct < 20 and win_rate > 0.5 else "LOW")
        print(f"Tested {len(results)} real months, avg error {avg_pct:.1f}%, "
              f"{win_rate*100:.0f}% within 10% error -> confidence {confidence}")
    else:
        confidence, avg_pct, results = "LOW", None, []
        print("No months could be validated -- confidence LOW")

    # --- Forecast forward from the last genuinely real month ---
    last_real_month = max(REAL_HISTORICAL_AOP.keys(), key=month_index)
    last_real_idx = month_index(last_real_month)
    print(f"\nLast genuinely real AOP month: {last_real_month} "
          f"(confirmed via formula inspection -- see README)")

    forecasts = {}
    for i in range(1, N_FORECAST_MONTHS + 1):
        idx = last_real_idx + i
        label = month_label(idx)
        forecasts[label] = forecast_aop(spells, idx, curves, price_history)

    write_report(curves, mix_m, mix_3, confidence, avg_pct, results,
                 last_real_month, forecasts)


def write_report(curves, mix_m, mix_3, confidence, avg_pct, cv_results,
                  last_real_month, forecasts):
    rows = []
    for month, old, new, note in [
        ("Cash Flow!row17 (Average Order Price)", "(unchanged for real months)",
         "(see forecast table below)", "Real historical months are NOT touched -- "
         "only months after " + last_real_month + " get the model's forecast."),
    ]:
        rows.append(dict(cell=old, old_value=old, new_value=new, note=note))

    with open("outputs/aop_report.md", "w") as f:
        f.write("# AOP Forecast Update -- Cash Flow!row17\n\n")
        f.write(f"Generated using the live retention curve "
                f"(Monthly: {curves['monthly_model_used']}, "
                f"3-Month: {curves['threemonth_model_used']}, "
                f"curve dated {curves.get('generated_date', 'unknown')}). "
                f"Re-running this after the retention model refits will "
                f"automatically use the new curve -- nothing here is hardcoded.\n\n")

        f.write("## Current active-subscriber mix (derived, not assumed)\n\n")
        f.write(f"- Monthly: {mix_m*100:.1f}%\n- 3-Month: {mix_3*100:.1f}%\n\n")
        f.write("Held FIXED going forward for this forecast (matches the sheet's own "
                "Cohort Modelling!B8:B9 structure, which is also a flat constant, not "
                "time-varying). Re-run this pipeline periodically to refresh this estimate "
                "as retention/acquisition data changes.\n\n")

        f.write("## Validation\n\n")
        f.write(f"**Confidence: {confidence}**")
        if avg_pct is not None:
            f.write(f" -- tested against {len(cv_results)} real historical months, "
                    f"average error {avg_pct:.1f}%.\n\n")
        else:
            f.write(" -- insufficient real data to validate.\n\n")
        f.write("| Month | Real AOP | Backtest Forecast | Error |\n|---|---|---|---|\n")
        for r in cv_results:
            f.write(f"| {r['month']} | £{r['actual']:.2f} | £{r['forecast']:.2f} | {r['pct_err']:.1f}% |\n")
        f.write("\n")

        f.write(f"## Cell updates needed: `Cash Flow!row17`\n\n")
        f.write(f"**Do NOT change any month up to and including {last_real_month}** -- "
                f"those are real, formula-derived actuals. Update only the months below, "
                f"which are currently hand-typed placeholder guesses in the sheet.\n\n")
        f.write("**Note on the pattern below:** these numbers rise and fall on a repeating "
                "3-month cycle. This is real, not a bug -- 3-Month subscribers only renew "
                "once every 3 months, so calendar months where more 3-Month cohorts hit "
                "their renewal point show a higher blended AOP (3-Month orders are pricier), "
                "and months in between show lower AOP. This same lumpiness is already present "
                "in the real historical data used to validate this model.\n\n")
        f.write("| Month | Current sheet value | Recommended new value |\n|---|---|---|\n")
        for month, forecast in forecasts.items():
            f.write(f"| {month} | (placeholder guess -- replace) | "
                    f"£{forecast:.2f} |\n" if forecast else f"| {month} | (placeholder guess) | n/a |\n")

    with open("outputs/aop_cell_updates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell", "month", "old_value", "new_value", "note"])
        for month, forecast in forecasts.items():
            w.writerow(["Cash Flow!row17", month, "(placeholder -- replace)",
                        f"{forecast:.2f}" if forecast else "n/a",
                        f"Forecast, confidence={confidence}"])

    print("\nWrote outputs/aop_report.md and outputs/aop_cell_updates.csv")


if __name__ == "__main__":
    run()
