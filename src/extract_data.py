"""
Extract cohort survivor-count series for the Monthly and 3-Month segments from
the DITTO financial model's appendix sheets (raw Klar/Appstle export data).

MONTHLY plan: the raw per-tenure-month subscriber counts in the top table are
used directly as survivor counts (billing is monthly, so tenure-month ==
billing-cycle number).

3-MONTH plan: the raw per-calendar-month counts are billing *events*, not
survivor counts -- because billing happens every 3 months, a customer shows
up as a spike in whichever exact calendar month their renewal charge landed,
which is noisy at monthly resolution. The sheet's own 'RETENTION' % table
(computed from the same underlying data) is smooth and monotonic when sampled
at the actual quarterly checkpoints (month 0, 3, 6, 9, ...). We resample that
table at quarterly checkpoints and multiply by cohort size (month-0 count) to
recover survivor counts per renewal cycle. This mirrors what the existing
Cohort Modelling sheet already does (its 3-Month Retention Curve block also
samples at End-of-Month 0/3/6/9/...).

Output:
  data/monthly_counts.csv      cohort_month, tenure_months, survivors
  data/threemonth_counts.csv   cohort_month, tenure_cycles (x3 months), survivors
"""
import re
import csv
import openpyxl

SRC = "model.xlsx"
COHORT_RE = re.compile(r"^\d{4}-\d{2}$")
MONTH_RE = re.compile(r"^MONTH\s+(\d+)$")


def month_col_map(header):
    cols = {}
    for j, v in enumerate(header):
        if isinstance(v, str):
            m = MONTH_RE.match(v.strip())
            if m:
                cols[int(m.group(1))] = j
    return cols


def extract_monthly(wb):
    ws = wb["APPENDIX Monthly Subscription R"]
    rows = list(ws.iter_rows(values_only=True))
    cols = month_col_map(rows[2])
    max_t = max(cols)
    records = []
    for row in rows[3:]:
        label = row[0]
        if isinstance(label, str) and not COHORT_RE.match(label):
            break  # hit the next section (RETENTION / CHURN / AVERAGE)
        if not (isinstance(label, str) and COHORT_RE.match(label)):
            continue
        for t in range(0, max_t + 1):
            j = cols.get(t)
            val = row[j] if j is not None and j < len(row) else None
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            records.append((label, t, val))
    return records


def extract_threemonth(wb):
    ws = wb["APPENDIX 3-Month Subscription R"]
    rows = list(ws.iter_rows(values_only=True))

    ret_start = None
    for i, row in enumerate(rows):
        if row and isinstance(row[0], str) and row[0].strip().upper() == "RETENTION":
            ret_start = i
            break
    if ret_start is None:
        raise RuntimeError("RETENTION section not found in 3-month sheet")

    top_cols = month_col_map(rows[2])
    cohort_size = {}
    for row in rows[3:ret_start]:
        label = row[0]
        if isinstance(label, str) and COHORT_RE.match(label):
            j0 = top_cols[0]
            v = row[j0] if j0 < len(row) else None
            if v is not None:
                cohort_size[label] = float(v)

    header_is_next = not any(
        isinstance(v, str) and MONTH_RE.match(v.strip()) for v in rows[ret_start]
    )
    ret_header = rows[ret_start + 1] if header_is_next else rows[ret_start]
    ret_cols = month_col_map(ret_header)
    body_start = ret_start + (2 if header_is_next else 1)

    max_t = max(ret_cols)
    quarter_tenures = [t for t in range(0, max_t + 1) if t % 3 == 0]

    records = []
    for row in rows[body_start:]:
        label = row[0]
        if isinstance(label, str) and not COHORT_RE.match(label):
            break  # hit the next section (e.g. 'AVERAGE', blank, 'CHURN')
        if not (isinstance(label, str) and COHORT_RE.match(label)):
            continue
        n0 = cohort_size.get(label)
        if not n0:
            continue
        for t in quarter_tenures:
            j = ret_cols.get(t)
            val = row[j] if j is not None and j < len(row) else None
            if val is None:
                continue
            try:
                frac = float(val)
            except (TypeError, ValueError):
                continue
            survivors = round(frac * n0)
            records.append((label, t // 3, survivors))
    return records


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)

    monthly = extract_monthly(wb)
    with open("data/monthly_counts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort_month", "tenure_months", "survivors"])
        w.writerows(monthly)
    print(f"monthly: {len(monthly)} rows")

    threemonth = extract_threemonth(wb)
    with open("data/threemonth_counts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort_month", "tenure_cycles", "survivors"])
        w.writerows(threemonth)
    print(f"3-month: {len(threemonth)} rows")


if __name__ == "__main__":
    main()
