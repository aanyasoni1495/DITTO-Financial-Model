"""
Shifted-Beta-Geometric (sBG) retention model: fitting + walk-forward backtest.

Core model (Fader & Hardie):
    S(t) = B(alpha, beta+t) / B(alpha, beta)          survival function
    P(t) = S(t-1) - S(t)                              unconditional churn-in-period-t prob

Fitting: pooled MLE across all cohorts. For each cohort we know, at each tenure t,
how many of the original cohort are still active. We treat the last *observed*
tenure for a cohort as right-censored (still active, future unknown).

Log-likelihood for one cohort observed up to tenure T_c:
    sum_{t=1}^{T_c-1} d_t * log(P(t))  +  s_{T_c} * log(S(T_c))
  where d_t = survivors(t-1) - survivors(t)   [churned exactly at tenure t]
        s_{T_c} = survivors(T_c)               [still active, right-censored]
"""
import csv
import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.special import betaln
from scipy.optimize import minimize


def load_series(path, tenure_col):
    data = defaultdict(dict)
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            cohort = row["cohort_month"]
            t = int(row[tenure_col])
            s = float(row["survivors"])
            data[cohort][t] = s
    return data


def clean_monotonic(series):
    """Enforce non-increasing survivor counts (reactivations/noise -> running min)."""
    ts = sorted(series)
    out = {}
    running_min = None
    for t in ts:
        v = series[t]
        running_min = v if running_min is None else min(running_min, v)
        out[t] = running_min
    return out


def cohort_month_index(label):
    """'2025-03' -> 2025*12+3, so calendar distance is just subtraction."""
    y, m = label.split("-")
    return int(y) * 12 + int(m)


def log_S(t, alpha, beta):
    if t == 0:
        return 0.0
    return betaln(alpha, beta + t) - betaln(alpha, beta)


def log_churn_prob(t, alpha, beta):
    """log(S(t-1) - S(t)), computed stably."""
    ls0 = log_S(t - 1, alpha, beta)
    ls1 = log_S(t, alpha, beta)
    # S(t-1) - S(t) = S(t-1) * (1 - S(t)/S(t-1))
    diff_ratio = 1 - math.exp(ls1 - ls0)
    diff_ratio = max(diff_ratio, 1e-12)
    return ls0 + math.log(diff_ratio)


@dataclass
class CohortObs:
    n0: float
    censor_t: int
    censor_survivors: float
    defections: dict  # t -> count churned exactly at t (for 1..censor_t-1)


def build_obs(series_by_cohort, cutoff_tenure=None, cutoff_calendar=None):
    """
    series_by_cohort: {cohort_label: {t: survivors}} (already cleaned monotonic)
    cutoff_calendar: if given, an integer calendar-month-index; a cohort's data is
        truncated to only tenures whose calendar month <= cutoff_calendar
        (this is what makes the backtest genuinely time-honest).
    """
    obs = []
    for cohort, series in series_by_cohort.items():
        ts = sorted(series)
        if 0 not in series:
            continue
        n0 = series[0]
        if n0 <= 0:
            continue

        if cutoff_calendar is not None:
            base = cohort_month_index(cohort)
            ts = [t for t in ts if base + t <= cutoff_calendar]
        if cutoff_tenure is not None:
            ts = [t for t in ts if t <= cutoff_tenure]
        if not ts:
            continue

        censor_t = max(ts)
        defections = {}
        for i in range(1, len(ts)):
            t_prev, t_cur = ts[i - 1], ts[i]
            if t_cur - t_prev == 1:  # only count consecutive-period defections cleanly
                d = series[t_prev] - series[t_cur]
                if d > 0:
                    defections[t_cur] = d
        obs.append(CohortObs(n0=n0, censor_t=censor_t,
                              censor_survivors=series[censor_t], defections=defections))
    return obs


def neg_log_likelihood(params, obs_list):
    alpha, beta = params
    if alpha <= 0 or beta <= 0:
        return 1e10
    ll = 0.0
    for o in obs_list:
        for t, d in o.defections.items():
            ll += d * log_churn_prob(t, alpha, beta)
        ll += o.censor_survivors * log_S(o.censor_t, alpha, beta)
    return -ll


def fit_sbg(obs_list, x0=(1.0, 3.0)):
    res = minimize(
        neg_log_likelihood, x0=np.array(x0), args=(obs_list,),
        method="L-BFGS-B", bounds=[(1e-3, 1000), (1e-3, 1000)],
    )
    return res.x  # alpha, beta


def predict_curve(alpha, beta, max_t):
    return [math.exp(log_S(t, alpha, beta)) for t in range(max_t + 1)]
