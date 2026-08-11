"""
Fits sBG and BdW on the SAME data, through the SAME time-series CV folds, and
reports which one actually predicts held-out data better -- the only fair
test of whether BdW's extra parameter (c) earns its keep or just overfits.

Does NOT compare "fit quality on training data" -- BdW can never look worse
than sBG there by construction (c=1 makes them identical), so that comparison
would be meaningless. Held-out accuracy is the only test that can tell them
apart honestly.

    python3 src/compare_models.py
"""
from sbg_model import load_series, clean_monotonic, build_obs, fit_sbg, predict_curve
from bdw_model import fit_bdw, predict_curve_bdw
from cross_validate import time_series_cv, summarize, confidence_rating


def bdw_bound_check(params):
    alpha, beta, c = params
    # same alpha/beta bound check as sBG, plus: c pinned near its own bounds
    # (0.1 or 5.0) means the data pushed it to an extreme with no real signal
    return (alpha > 500 or beta > 500 or alpha < 0.01 or beta < 0.01
            or c < 0.15 or c > 4.8)


def run_comparison(csv_path, tenure_col, sheet_curve, n_splits, min_train_frac,
                    max_t, label):
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    raw = load_series(csv_path, tenure_col)
    cleaned = {c: clean_monotonic(s) for c, s in raw.items()}

    # Full-data fits (for reference -- the CV below is what actually matters)
    alpha_s, beta_s = fit_sbg(build_obs(cleaned))
    alpha_b, beta_b, c_b = fit_bdw(build_obs(cleaned))
    print(f"sBG full fit: alpha={alpha_s:.4f}, beta={beta_s:.4f}")
    print(f"BdW full fit: alpha={alpha_b:.4f}, beta={beta_b:.4f}, c={c_b:.4f}"
          f"  ({'close to sBG (c~1)' if abs(c_b-1) < 0.1 else 'meaningfully different from sBG'})")

    print(f"\n--- sBG cross-validation ---")
    cv_sbg = summarize(
        time_series_cv(cleaned, predict_curve, sheet_curve, n_splits=n_splits,
                        min_train_frac=min_train_frac, max_t=max_t,
                        fit_fn=fit_sbg),
        "sBG vs sheet")
    conf_sbg, reason_sbg = confidence_rating(cv_sbg)

    print(f"\n--- BdW cross-validation ---")
    cv_bdw = summarize(
        time_series_cv(cleaned, predict_curve_bdw, sheet_curve, n_splits=n_splits,
                        min_train_frac=min_train_frac, max_t=max_t,
                        fit_fn=fit_bdw, bound_check=bdw_bound_check),
        "BdW vs sheet")
    conf_bdw, reason_bdw = confidence_rating(cv_bdw)

    print(f"\n--- Head-to-head: sBG vs BdW, same held-out points ---")
    if cv_sbg and cv_bdw:
        print(f"sBG:  MAE={cv_sbg['mae_new']:.4f}  confidence={conf_sbg}")
        print(f"BdW:  MAE={cv_bdw['mae_new']:.4f}  confidence={conf_bdw}")
        if cv_bdw['mae_new'] < cv_sbg['mae_new']:
            improvement = 100 * (1 - cv_bdw['mae_new'] / cv_sbg['mae_new'])
            print(f"-> BdW beats sBG by {improvement:.1f}% on held-out data.")
            if conf_bdw in ("LOW",) and conf_sbg in ("HIGH", "MEDIUM"):
                print(f"   CAUTION: BdW's win comes with a LOWER confidence rating than sBG's "
                      f"({conf_bdw} vs {conf_sbg}) -- likely overfitting given the extra "
                      f"parameter, not a genuine improvement. Recommend keeping sBG.")
            else:
                print(f"   BdW's confidence rating ({conf_bdw}) is not worse than sBG's "
                      f"({conf_sbg}) -- this looks like a genuine improvement worth adopting.")
        else:
            worse = 100 * (cv_bdw['mae_new'] / cv_sbg['mae_new'] - 1)
            print(f"-> BdW is {worse:.1f}% WORSE than sBG on held-out data. "
                  f"The extra parameter (c) is overfitting, not helping. Keep sBG.")
    else:
        print("One or both models produced no usable CV folds -- cannot compare.")

    return dict(sbg=(alpha_s, beta_s), bdw=(alpha_b, beta_b, c_b),
                cv_sbg=cv_sbg, cv_bdw=cv_bdw, conf_sbg=conf_sbg, conf_bdw=conf_bdw)


if __name__ == "__main__":
    SHEET_MONTHLY = [1.0,0.7170083903,0.5566790632,0.4422522947,0.367300401,0.311674408,0.2591459491,
                     0.2487801112,0.2388289067,0.2292757504,0.2201047204,0.2113005316,0.2028485103,
                     0.1987915401,0.1948157093,0.1909193951,0.1871010072,0.1833589871,0.1796918074,
                     0.1760979712,0.1725760118,0.1691244916,0.1657420017,0.1624271617,0.1591786185]
    SHEET_3MONTH_CYCLES = [1.0, 0.5817337683, 0.3246622985, 0.1952197031, 0.1800085743,
                           0.1694226301, 0.159459224, 0.150081746, 0.1426971238]

    run_comparison("data/monthly_counts.csv", "tenure_months", SHEET_MONTHLY,
                    n_splits=5, min_train_frac=0.4, max_t=24, label="MONTHLY: sBG vs BdW")
    run_comparison("data/threemonth_counts.csv", "tenure_cycles", SHEET_3MONTH_CYCLES,
                    n_splits=4, min_train_frac=0.3, max_t=8, label="3-MONTH: sBG vs BdW")
