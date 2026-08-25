"""
Final validation of the subscriber-matched AOP forecast: time-series
backtest (multiple cutoffs, never let the model see the future) against
every genuinely real historical month we have, not just a handful.

REAL_HISTORICAL_AOP months are ground truth (sheet's own formula-derived
values, confirmed by inspecting the actual formulas -- see
build_aop_forecast.py / validate_aop_pipeline.py for how 2026-08 onward
was confirmed to be a placeholder, not real, and excluded).
"""
import json
from collections import defaultdict
from forecast_aop import load_cohorts, load_price_history, forecast_aop, month_index

REAL_HISTORICAL_AOP = {
    "2025-03": 65.68422222, "2025-04": 53.02836879, "2025-05": 46.69518717,
    "2025-06": 51.61857678, "2025-07": 49.16032609, "2025-08": 44.5221309,
    "2025-09": 43.25529101, "2025-10": 42.27181509, "2025-11": 37.60886513,
    "2025-12": 33.95110806, "2026-01": 33.21705562, "2026-02": 33.60864525,
    "2026-03": 33.65540714, "2026-04": 34.17240122, "2026-05": 35.82098181,
    "2026-06": 37.90426075, "2026-07": 41.08977107,
}


def real_acquisitions_for_month(spells, month):
    """
    For backtesting: use the REAL, actual acquisitions that happened in
    `month` (known from spells, since it already happened), not the
    sheet's forward-looking forecast -- that's the correct comparison for
    validating the model's accuracy on real historical data. The sheet's
    forecast is only used for genuinely FUTURE months in run_aop_pipeline.py.
    """
    counts = defaultdict(int)
    for s in spells:
        if s["signup_month"] == month:
            counts[s["plan"]] += 1
    return {"monthly": counts.get("Monthly", 0), "threemonth": counts.get("3-Month", 0)}


def run_backtest(spells, curves, price_history, test_months, min_history_months=3):
    import forecast_aop as fa
    results = []
    for month in test_months:
        idx = month_index(month)
        earliest = min(month_index(m) for m in REAL_HISTORICAL_AOP)
        if idx - earliest < min_history_months:
            continue

        # Build a one-month "sheet_acquisitions" dict using the REAL
        # acquisitions that actually happened that month (not a forecast --
        # this month already happened, so we know the true volume).
        real_acq = {month: real_acquisitions_for_month(spells, month)}

        # Likewise, use THIS month's real average first-order price, not a
        # fixed August price -- August-pinning is a forward-looking-forecast
        # choice (see run_aop_pipeline.py), not appropriate when validating
        # against a specific different historical month.
        month_spells_m = [s for s in spells if s["plan"] == "Monthly" and s["signup_month"] == month]
        month_spells_3 = [s for s in spells if s["plan"] == "3-Month" and s["signup_month"] == month]
        original_price = dict(fa.AUGUST_AVG_PRICE)
        if month_spells_m:
            fa.AUGUST_AVG_PRICE["Monthly"] = sum(s["first_order_paid"] for s in month_spells_m) / len(month_spells_m)
        if month_spells_3:
            fa.AUGUST_AVG_PRICE["3-Month"] = sum(s["first_order_paid"] for s in month_spells_3) / len(month_spells_3)

        forecast = fa.forecast_aop(spells, idx, curves, price_history, real_acq, cutoff_month_idx=idx)
        fa.AUGUST_AVG_PRICE = original_price  # restore, so other test months aren't affected

        actual = REAL_HISTORICAL_AOP.get(month)
        if forecast is None or actual is None:
            continue

        abs_err = abs(forecast - actual)
        pct_err = abs_err / actual * 100
        results.append(dict(month=month, actual=actual, forecast=forecast,
                             abs_err=abs_err, pct_err=pct_err))
    return results


if __name__ == "__main__":
    spells = load_cohorts("data/customer_cohorts.csv")
    with open("docs/curves.json") as f:
        curves = json.load(f)
    price_history = load_price_history("data/price_history.json")

    # test every real month we can, not just the last 3 -- proper coverage
    test_months = sorted(REAL_HISTORICAL_AOP.keys())

    print("=== Time-series backtest across ALL testable real months ===\n")
    results = run_backtest(spells, curves, price_history, test_months, min_history_months=3)

    print(f"{'Month':<10}{'Actual':<10}{'Forecast':<11}{'Abs Err':<10}{'% Err'}")
    for r in results:
        print(f"{r['month']:<10}£{r['actual']:<9.2f}£{r['forecast']:<10.2f}£{r['abs_err']:<9.2f}{r['pct_err']:.1f}%")

    if results:
        avg_pct = sum(r["pct_err"] for r in results) / len(results)
        max_pct = max(r["pct_err"] for r in results)
        print(f"\nTested {len(results)} real months")
        print(f"Average % error: {avg_pct:.1f}%")
        print(f"Worst single-month % error: {max_pct:.1f}%")

        # confidence, same discipline as the retention model: check
        # consistency, not just average
        n_good = sum(1 for r in results if r["pct_err"] < 10)
        win_rate = n_good / len(results)
        print(f"Months within 10% error: {n_good}/{len(results)} ({win_rate*100:.0f}%)")

        if avg_pct < 8 and win_rate > 0.8:
            confidence = "HIGH"
        elif avg_pct < 20 and win_rate > 0.5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        print(f"\nConfidence: {confidence}")
    else:
        print("No months could be tested -- insufficient history. Confidence: LOW")

    # --- Rolling-origin cross-validation: multiple expanding-window folds,
    # same discipline as the retention model's time_series_cv ---
    print("\n\n=== Rolling-origin cross-validation (expanding window folds) ===\n")
    sorted_months = sorted(REAL_HISTORICAL_AOP.keys(), key=month_index)
    n_folds = 4
    fold_size = max(1, len(sorted_months) // (n_folds + 2))  # leave room for min history
    fold_maes = []
    for fold in range(n_folds):
        test_start = 4 + fold * fold_size  # skip first few months as minimum history
        test_end = min(test_start + fold_size, len(sorted_months))
        if test_start >= len(sorted_months) or test_end <= test_start:
            continue
        fold_test_months = sorted_months[test_start:test_end]
        fold_results = run_backtest(spells, curves, price_history, fold_test_months, min_history_months=1)
        if not fold_results:
            continue
        fold_mae = sum(r["abs_err"] for r in fold_results) / len(fold_results)
        fold_maes.append(fold_mae)
        print(f"Fold {fold}: test months {fold_test_months}, MAE=£{fold_mae:.2f}")

    if fold_maes:
        print(f"\nAverage MAE across {len(fold_maes)} folds: £{sum(fold_maes)/len(fold_maes):.2f}")
