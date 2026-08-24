"""
Writes docs/curves.json from the currently fitted retention models -- run
this as the last step of run_pipeline.py, every time new monthly data comes
in. The AOV simulator (docs/aov_simulator.html) fetches this file on load,
so pushing a fresh curves.json is the only step needed to update the live
tool with the latest fitted curve.
"""
import json
import math
from datetime import date
import numpy as np
from scipy.special import betaln
from scipy.optimize import minimize

def log_S(t, alpha, beta):
    if t == 0: return 0.0
    return betaln(alpha, beta+t) - betaln(alpha, beta)

def log_churn_prob(t, alpha, beta):
    ls0 = log_S(t-1, alpha, beta); ls1 = log_S(t, alpha, beta)
    diff_ratio = max(1 - math.exp(ls1-ls0), 1e-12)
    return ls0 + math.log(diff_ratio)

def nll(params, obs_list):
    alpha, beta = params
    if alpha <= 0 or beta <= 0: return 1e10
    ll = 0.0
    for o in obs_list:
        for t,d in o['defections'].items(): ll += d*log_churn_prob(t,alpha,beta)
        ll += o['censor_survivors']*log_S(o['censor_t'],alpha,beta)
    return -ll

def fit_sbg(obs_list, x0=(1.0,3.0)):
    res = minimize(nll, x0=np.array(x0), args=(obs_list,), method="L-BFGS-B", bounds=[(1e-3,1000),(1e-3,1000)])
    return res.x

def predict_curve(alpha, beta, max_t):
    return [math.exp(log_S(t,alpha,beta)) for t in range(max_t+1)]

def export(monthly_obs, threemonth_obs, monthly_model_used="sBG", threemonth_model_used="sBG",
           monthly_curve=None, threemonth_curve=None, output_path="docs/curves.json"):
    """
    Fits sBG on both plans by default. monthly_curve/threemonth_curve can be
    passed in directly if you've already fit elsewhere (e.g. inside
    run_pipeline.py) and just want this function to write the JSON.
    """
    if monthly_curve is None:
        alpha_m, beta_m = fit_sbg(monthly_obs)
        monthly_curve = predict_curve(alpha_m, beta_m, 48)
    if threemonth_curve is None:
        alpha_3, beta_3 = fit_sbg(threemonth_obs)
        threemonth_curve = predict_curve(alpha_3, beta_3, 16)

    data = {
        "generated_date": date.today().isoformat(),
        "monthly_curve": [round(x, 6) for x in monthly_curve],
        "monthly_model_used": monthly_model_used,
        "threemonth_curve_cycles": [round(x, 6) for x in threemonth_curve],
        "threemonth_model_used": threemonth_model_used,
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {output_path} (generated {data['generated_date']})")
    return data

import csv
from collections import defaultdict

def load_series(path, tenure_col):
    data = defaultdict(dict)
    with open(path) as f:
        for row in csv.DictReader(f):
            data[row["cohort_month"]][int(row[tenure_col])] = float(row["survivors"])
    return data

def clean_monotonic(series):
    ts = sorted(series)
    out, running_min = {}, None
    for t in ts:
        v = series[t]
        running_min = v if running_min is None else min(running_min, v)
        out[t] = running_min
    return out

def build_obs(cleaned):
    obs = []
    for cohort, series in cleaned.items():
        ts = sorted(series)
        if 0 not in series: continue
        n0 = series[0]
        if n0 <= 0: continue
        censor_t = max(ts)
        defections = {}
        for i in range(1, len(ts)):
            tp, tc = ts[i-1], ts[i]
            if tc - tp == 1:
                d = series[tp] - series[tc]
                if d > 0: defections[tc] = d
        obs.append(dict(n0=n0, censor_t=censor_t, censor_survivors=series[censor_t], defections=defections))
    return obs


if __name__ == "__main__":
    # Refits both plans using sBG from data/monthly_counts.csv and
    # data/threemonth_counts.csv, and writes docs/curves.json.
    raw_m = load_series("data/monthly_counts.csv", "tenure_months")
    clean_m = {c: clean_monotonic(s) for c, s in raw_m.items()}
    raw_3 = load_series("data/threemonth_counts.csv", "tenure_cycles")
    clean_3 = {c: clean_monotonic(s) for c, s in raw_3.items()}

    export(build_obs(clean_m), build_obs(clean_3))
