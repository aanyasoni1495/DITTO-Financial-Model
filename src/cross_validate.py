"""
Time-series cross-validation for the sBG retention model.

Unlike a single arbitrary train/test cutoff, this creates several folds, each
with an expanding training window and a non-overlapping test window right
after it -- the cohort-data equivalent of sklearn's TimeSeriesSplit. This
means later folds have more training data (more realistic -- that's how the
model will actually be used, refit each month on everything so far) and no
data point is scored by more than one fold, so the aggregate MAE isn't
inflated by re-using the same easy/hard points repeatedly.

Used both to validate the raw sBG curve AND the flat-tier approximation that
actually gets pasted into the sheet (these are different questions -- see
business_impact.py for why the second one matters separately).
"""
from dataclasses import dataclass
from sbg_model import cohort_month_index, build_obs, fit_sbg, predict_curve


@dataclass
class FoldResult:
    fold: int
    cutoff_calendar: int
    n_train_points: int
    n_test_points: int
    mae_new: float
    mae_old: float
    alpha: float
    beta: float
    hit_bound: bool  # True if the fit landed suspiciously close to the optimizer's bounds
    # (a sign of too little training data for this fold -- see summarize())


def _calendar_range(cleaned):
    lo, hi = None, None
    for cohort, series in cleaned.items():
        base = cohort_month_index(cohort)
        for t in series:
            cal = base + t
            lo = cal if lo is None else min(lo, cal)
            hi = cal if hi is None else max(hi, cal)
    return lo, hi


def time_series_cv(cleaned, curve_fn, old_curve, n_splits=5, min_train_frac=0.5,
                    max_t=None):
    """
    cleaned: {cohort: {t: survivors}}, already monotonic-cleaned
    curve_fn: function(alpha, beta, max_t) -> list of survival fractions
              (pass predict_curve directly for the raw curve, or a wrapper
              that applies the flat-tier approximation for that check)
    old_curve: the current sheet's curve (same indexing as curve_fn's output),
               to compare against
    """
    lo, hi = _calendar_range(cleaned)
    span = hi - lo
    if max_t is None:
        max_t = span

    test_start = lo + int(span * min_train_frac)
    window = max(1, (hi - test_start) // n_splits)

    results = []
    for i in range(n_splits):
        cutoff = test_start + i * window
        test_end = cutoff + window if i < n_splits - 1 else hi

        obs_train = build_obs(cleaned, cutoff_calendar=cutoff)
        if not obs_train:
            continue
        alpha, beta = fit_sbg(obs_train)
        new_curve = curve_fn(alpha, beta, max_t)

        errs_new, errs_old = [], []
        for cohort, series in cleaned.items():
            base = cohort_month_index(cohort)
            n0 = series.get(0)
            if not n0:
                continue
            for t, survivors in series.items():
                cal = base + t
                if not (cutoff < cal <= test_end):
                    continue
                if t >= len(new_curve):
                    continue
                actual = survivors / n0
                errs_new.append(abs(new_curve[t] - actual))
                old_val = old_curve[t] if t < len(old_curve) else old_curve[-1]
                errs_old.append(abs(old_val - actual))

        if not errs_new:
            continue
        hit_bound = alpha > 500 or beta > 500 or alpha < 0.01 or beta < 0.01
        results.append(FoldResult(
            fold=i, cutoff_calendar=cutoff,
            n_train_points=sum(len(o.defections) + 1 for o in obs_train),
            n_test_points=len(errs_new),
            mae_new=sum(errs_new) / len(errs_new),
            mae_old=sum(errs_old) / len(errs_old),
            alpha=alpha, beta=beta, hit_bound=hit_bound,
        ))
    return results


def summarize(results, label):
    if not results:
        print(f"{label}: no folds produced usable test points")
        return None
    n_total = sum(r.n_test_points for r in results)
    weighted_new = sum(r.mae_new * r.n_test_points for r in results) / n_total
    weighted_old = sum(r.mae_old * r.n_test_points for r in results) / n_total
    n_folds_improved = sum(1 for r in results if r.mae_new < r.mae_old)
    win_rate = n_folds_improved / len(results)
    any_bound_hit = any(r.hit_bound for r in results)

    print(f"\n{label} -- {len(results)} folds, {n_total} total held-out points")
    for r in results:
        flag = " [HIT OPTIMIZER BOUND -- unstable fit, too little data]" if r.hit_bound else ""
        print(f"  fold {r.fold}: {r.n_test_points} pts, "
              f"new MAE={r.mae_new:.4f}, old MAE={r.mae_old:.4f}, "
              f"alpha={r.alpha:.2f}, beta={r.beta:.2f}{flag}")
    print(f"  weighted avg: new MAE={weighted_new:.4f}, old MAE={weighted_old:.4f} "
          f"({'IMPROVEMENT' if weighted_new < weighted_old else 'NO IMPROVEMENT'}, "
          f"{100*(1-weighted_new/weighted_old):+.1f}%)")
    print(f"  won {n_folds_improved}/{len(results)} folds ({win_rate*100:.0f}%)")

    return dict(n_folds=len(results), n_points=n_total,
                mae_new=weighted_new, mae_old=weighted_old,
                improved=weighted_new < weighted_old,
                win_rate=win_rate, any_bound_hit=any_bound_hit)


def confidence_rating(cv_result):
    """
    Returns (label, reason) -- a plain-English justification, not just a tier
    name. Criteria, in order of what actually matters for trusting a fold-CV
    result:
      1. Does it even beat the old numbers on data it wasn't fit on?
      2. Is that true consistently across folds, or only on average (a few
         good folds hiding several bad ones)?
      3. Is there enough held-out data for the result to mean something?
      4. Did any fold's fit degenerate (hit the optimizer's bounds) -- a sign
         that fold simply didn't have enough training data to fit reliably?
    """
    if cv_result is None:
        return "LOW", "Cross-validation produced no usable folds at all."

    n = cv_result["n_points"]
    win_rate = cv_result["win_rate"]
    improved = cv_result["improved"]
    bound_hit = cv_result["any_bound_hit"]

    if not improved:
        return "LOW", (f"On aggregate, the new numbers did NOT beat the old ones "
                        f"across {cv_result['n_folds']} folds / {n} held-out points "
                        f"(MAE {cv_result['mae_new']:.4f} vs {cv_result['mae_old']:.4f}). "
                        f"Do not trust this over the current sheet value.")

    if bound_hit:
        return "LOW", (f"Aggregate MAE improved ({cv_result['mae_new']:.4f} vs "
                        f"{cv_result['mae_old']:.4f}), but at least one fold's fit hit the "
                        f"optimizer's bound (alpha or beta pushed to an extreme value) -- "
                        f"a sign that fold simply didn't have enough training data yet for "
                        f"a stable fit. Treat as directionally useful, not settled.")

    if n < 40 or win_rate < 0.6:
        return "MEDIUM", (f"Improved on aggregate ({cv_result['mae_new']:.4f} vs "
                           f"{cv_result['mae_old']:.4f}, won {win_rate*100:.0f}% of folds) "
                           f"but only {n} held-out points total, or wins aren't consistent "
                           f"across folds -- real signal, but a small-sample one.")

    return "HIGH", (f"Improved on aggregate ({cv_result['mae_new']:.4f} vs "
                     f"{cv_result['mae_old']:.4f}), won {win_rate*100:.0f}% of "
                     f"{cv_result['n_folds']} folds, {n} held-out points, no fold hit an "
                     f"optimizer bound. Consistent, well-supported result.")
