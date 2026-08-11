"""
Beta-discrete-Weibull (BdW) retention model (Fader, Hardie, Liu, Davin &
Steenburgh, 2018 -- "'How to Project Customer Retention' Revisited: The Role
of Duration Dependence").

Extends sBG by adding one parameter, c, which lets an INDIVIDUAL customer's
own churn probability drift up or down the longer they stay -- sBG assumes
each person's personal churn probability is fixed for life, and only the
population MIX (fast-churners leaving, hardcores remaining) changes over
time. BdW allows genuine within-person change on top of that.

Core model:
    S(t) = B(alpha, beta + t^c) / B(alpha, beta)     survival function
    P(t) = S(t-1) - S(t)                             unconditional churn-in-period-t prob

When c = 1, this is mathematically identical to sBG -- BdW can never fit
worse than sBG on the data it was FIT on, which is exactly why we don't just
compare training fit: see compare_models.py, which checks HELD-OUT accuracy
instead, the only fair test of whether the extra parameter (c) is earning
its keep or just overfitting.

Reuses sBG's data loading, cleaning, and observation-building (build_obs) --
identical data, identical censoring logic, so a comparison between the two
models is a comparison of the MATH only, not the data pipeline.
"""
import math
import numpy as np
from scipy.special import betaln
from scipy.optimize import minimize

from sbg_model import load_series, clean_monotonic, cohort_month_index, build_obs, CohortObs  # noqa: F401 (re-exported)


def log_S_bdw(t, alpha, beta, c):
    if t == 0:
        return 0.0
    return betaln(alpha, beta + t ** c) - betaln(alpha, beta)


def log_churn_prob_bdw(t, alpha, beta, c):
    ls0 = log_S_bdw(t - 1, alpha, beta, c)
    ls1 = log_S_bdw(t, alpha, beta, c)
    diff_ratio = 1 - math.exp(ls1 - ls0)
    diff_ratio = max(diff_ratio, 1e-12)
    return ls0 + math.log(diff_ratio)


def neg_log_likelihood_bdw(params, obs_list):
    alpha, beta, c = params
    if alpha <= 0 or beta <= 0 or c <= 0:
        return 1e10
    ll = 0.0
    for o in obs_list:
        for t, d in o.defections.items():
            ll += d * log_churn_prob_bdw(t, alpha, beta, c)
        ll += o.censor_survivors * log_S_bdw(o.censor_t, alpha, beta, c)
    return -ll


def fit_bdw(obs_list, x0=(1.0, 3.0, 1.0)):
    """
    x0's third value (c=1.0) deliberately starts BdW at exactly sBG's shape --
    if the data doesn't support c != 1, the optimizer should stay close to 1,
    not be pushed away from it by a biased starting guess.
    """
    res = minimize(
        neg_log_likelihood_bdw, x0=np.array(x0), args=(obs_list,),
        method="L-BFGS-B", bounds=[(1e-3, 1000), (1e-3, 1000), (0.1, 5.0)],
    )
    return res.x  # alpha, beta, c


def predict_curve_bdw(alpha, beta, c, max_t):
    return [math.exp(log_S_bdw(t, alpha, beta, c)) for t in range(max_t + 1)]
