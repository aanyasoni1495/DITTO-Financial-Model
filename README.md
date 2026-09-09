# DITTO Financial Model — Automated Data Pipeline

This repo replaces two sets of hand-typed assumptions in DITTO's Google Sheets
financial model with numbers derived from real Shopify order data:

1. **Retention/churn assumptions** (`Model Assumptions` and `Cohort Modelling`
   tabs) — fit with a shifted-Beta-Geometric (sBG) survival model.
2. **Average Order Price forecast** (`Cash Flow!row17`) — forecast from real
   renewal cohorts plus the sheet's own acquisition volume forecast.

It runs as a GitHub Actions workflow, triggered manually at month-end. It also
publishes a small interactive web tool (hosted on Vercel) where you can try
hypothetical future pricing/mix and get a ready-to-paste row of numbers for
`Cash Flow!row17`.

**Nothing in this pipeline writes into the live Google Sheet automatically —
it produces the correct numbers and you paste them in yourself.** See "Month-end
runbook" below for the exact steps and cell references.

---

## 1. Architecture at a glance

```
Google Drive (model.xlsx)  ─┐
Shopify Admin API           ├──▶  GitHub Actions ("Monthly Refresh")  ──▶  outputs/*.md, *.csv
                             │                                        ──▶  docs/*.json (committed to repo)
                             ┘                                                    │
                                                                                   ▼
                                                                     Vercel (auto-deploys docs/)
                                                                     → interactive AOP forecast page
```

- **Trigger**: manual only (`workflow_dispatch`), run at month-end after you've
  finished updating that month's real numbers in the sheet.
- **Auth to Google Drive**: Workload Identity Federation (WIF) — no service
  account key file stored anywhere. Google Cloud's
  `iam.disableServiceAccountKeyCreation` org policy blocks creating one
  anyway; GitHub's own OIDC token is exchanged for short-lived Google Cloud
  credentials at run time instead.
- **Auth to Shopify**: a stored Admin API access token (repo secret), generated
  via the OAuth authorization-code grant (install flow) — this produces a
  long-lived `shpat_...` token, not one that expires every 24 hours, so no
  token-refresh step is needed anywhere in the workflow.
- **Hosting**: the `docs/` folder is a static site, deployed on **Vercel**
  (migrated from Netlify after running out of Netlify's free-tier deploy
  credits). Vercel auto-redeploys on every push to `main` that touches `docs/`.
- **The live financial model (`model.xlsx`) is never committed to git.** It's
  downloaded fresh from Drive at the start of each run (picks the *most
  recently modified* file in the shared folder — the filename doesn't need to
  match exactly) and explicitly deleted at the end of the run
  (`.gitignore` also excludes it as a backstop).

---

## 2. Repo layout — what's where

```
data/                          Processed, pipeline-ready data (all regenerated each run)
  customer_cohorts.csv           One row per subscriber "spell": plan, signup month,
                                  first-order price paid, own recurring price, renewals observed
  orders_clean.csv               Every Shopify order, classified by plan (Monthly/3-Month/
                                  6-Month/Annual/OTP) and order_type (first_order/recurring).
                                  Plan comes from Appstle subscription TAGS, not product name
                                  (product naming changed twice in the export's history).
                                  Untagged orders = OTP (one-time purchase).
  price_history.json             Month-by-month DOMINANT list price per plan, detected from
                                  real first-order data (not assumed)
  sheet_acquisition_forecast.json  The sheet's OWN forecasted new-signup counts per month,
                                  per plan (Revenue Model!row9/row10) — read-only input, this
                                  pipeline never overrides the sheet's own growth assumptions
  monthly_counts.csv / threemonth_counts.csv   Cohort retention count tables (subscribers
                                  still active at each renewal cycle), used to fit the sBG curves

docs/                           Static site, deployed on Vercel
  aop_forecast.html               THE live tool — interactive AOP (row17) forecast page
  aop_data.json                   Data file aop_forecast.html reads (regenerated every run)
  curves.json                     Live retention curves (monthly_curve, threemonth_curve_cycles),
                                  regenerated every run
  index.html / aov_simulator.html  Older, simpler tenure-based AOV simulator (separate tool,
                                  not tied to Cash Flow!row17 — kept for reference)

outputs/                        Human-readable results from the last run (regenerated each time)
  report.md                       Retention model results: validation, confidence, and every
                                  "New value" to paste into Model Assumptions / Cohort Modelling
  sheet_updates.csv                Same, as a raw CSV
  aop_report.md                    AOP forecast narrative + validation + the pipeline's own
                                  single recommended row17 values (sheet's real acquisition
                                  mix + real recent average price — NOT the interactive tool's
                                  hypothetical scenarios)
  aop_cell_updates.csv             Same, as a raw CSV (old_value / new_value per month)
  monthly_sbg_curve.csv / threemonth_sbg_curve.csv   The fitted retention curves themselves

src/                            All pipeline code
  fetch_model_from_drive.py       Downloads the latest model.xlsx from the shared Drive folder
  extract_data.py                 Pulls cohort count tables out of model.xlsx's APPENDIX sheets
                                  (APPENDIX Monthly Subscription R, APPENDIX 3-Month Subscription
                                  R) — only the MONTH 0/1/2... count tables and RETENTION %
                                  sub-table. Deliberately does NOT use the per-subscriber ID/
                                  signup/cancellation-date export sitting further right in those
                                  same sheets — that field isn't reliably maintained. For 3-Month,
                                  raw month-by-month counts are billing-event noise (billing
                                  happens every 3 months), so this resamples the sheet's own
                                  RETENTION table at the actual quarterly checkpoints instead.
  run_pipeline.py                 Fits the sBG retention curves, cross-validates (time-series
                                  folds, expanding window — not a single arbitrary cutoff),
                                  writes outputs/report.md and outputs/sheet_updates.csv
  sbg_model.py                    The shifted-Beta-Geometric survival model itself (MLE fit,
                                  log-likelihood)
  cross_validate.py / run_backtest.py   Retention model validation helpers
  business_impact.py               Replicates the exact LTV/CAC formula chain from Cohort
                                  Modelling, to compute before/after impact without a full
                                  workbook recalc. IMPORTANT: hardcodes a handful of base
                                  assumptions (CAC, price, gross margin) copied from
                                  Cohort Modelling!B1:B12 at the time this was built — these do
                                  NOT auto-sync. If those change in the sheet, update the
                                  constants at the top of this file to match.
  export_curves.py                Writes docs/curves.json from the freshly fit curves
  fetch_shopify_orders_api.py     Pulls recent orders via Shopify Admin API, merges into
                                  data/orders_clean.csv (de-duplicated by order number, not a
                                  full replace — see "Shopify data" section below for why)
  extract_shopify_orders.py       Shared order-classification logic (plan + order_type from
                                  Appstle tags; untagged = OTP). Also used for one-time manual
                                  extraction from a raw CSV export.
  build_customer_cohorts.py       Rebuilds data/customer_cohorts.csv from orders_clean.csv
  detect_price_changes.py         Rebuilds data/price_history.json
  estimate_current_mix.py         Current ACTIVE-subscriber mix — projects every historical
                                  cohort forward through the live retention curve, rather than
                                  using raw new-signup mix (see "Why not last month's mix" below)
  forecast_aop.py                 Core AOP forecasting math (renewal decomposition, price
                                  resolution) — shared by run_aop_pipeline.py and
                                  export_aop_data.py
  run_aop_pipeline.py              Produces the pipeline's ONE grounded row17 recommendation
                                  (outputs/aop_report.md, aop_cell_updates.csv) — uses the
                                  sheet's own real acquisition mix, fixed going forward (see
                                  "Known limitation" under AOP below)
  export_aop_data.py               Produces docs/aop_data.json for the INTERACTIVE tool — the
                                  most complex file in the repo; see section 4 below
  validate_final.py               Backtest harness + REAL_HISTORICAL_AOP (known-real months,
                                  used only to score model confidence — no longer used to decide
                                  what's "real" for the live tool, see section 4)
  read_model_state.py              Reads assumption cells out of model.xlsx (e.g. OTP mix)
  generate_sheet_updates.py        Older/alternate script producing the same sheet_updates.csv
                                  format — not called by the automation (run_pipeline.py does
                                  the equivalent work); kept for reference/manual use

.github/workflows/monthly-refresh.yml   The whole automation, step by step (see section 3)
requirements.txt                 Python dependencies
```

---

## 3. Month-end runbook — exact steps

1. **Finish updating the sheet as normal.** Whatever number you type into last
   month's `Cash Flow!row17` cell, that's what this pipeline treats as the
   real, trusted actual for that month — see section 4 for exactly how "real
   vs. forecast" is decided now.
2. **Upload `model.xlsx`** to the shared Google Drive folder (the one shared
   with `ditto-pipeline-bot@...`), overwriting the previous file.
3. **GitHub → this repo → Actions tab → "Monthly Refresh" → Run workflow.**
   Confirm on the branch dropdown (`main`) and click the green button.
4. **Watch it run** — 15 steps, roughly 5–15 minutes depending on Shopify
   order volume. Each step should turn green. If anything fails, click into
   the failing step for the actual error (see section 7, "If something breaks").
5. **Open `outputs/report.md`** in the repo. It lists every retention-model
   cell that changed and its new value:
   - `Model Assumptions!C32` — Monthly M7–12 churn
   - `Model Assumptions!C33` — Monthly M13–24 churn
   - `Model Assumptions!C34` — Monthly post-M24 churn
   - `Model Assumptions!C43 / C44 / C45` — same three tiers for 3-Month
   - `Cohort Modelling!B20` — duplicate of C32 that also needs updating
   - `Cohort Modelling!K415` — the 3-Month month-9 fix (this one was applied
     by hand once already, replacing a formula with a static value — rerunning
     the pipeline just tells you what the *current* fitted value would be, for
     comparison; it won't auto-reapply)

   Copy each "New value" into that exact cell in the live sheet by hand.
6. **Open `outputs/aop_report.md`** (or `aop_cell_updates.csv`) for the
   pipeline's own single recommended set of `Cash Flow!row17` values.

   **Or**, for a value you actually control: open the live AOP Forecast page
   (Vercel URL + `/aop_forecast.html`), set your own price/discount/mix
   assumptions, and click **"Copy row17 for pasting into the sheet."** This
   copies one full tab-separated row — real months untouched, forecast months
   per your scenario, and any Year 1/2/3/4 summary cells the sheet has,
   recalculated live and correctly positioned. Paste directly into the first
   real month's cell in row17.
7. **Sanity-check** the validation section in `report.md` / `aop_report.md`
   (average error %, confidence rating) before trusting the numbers blindly.
   If confidence has dropped from HIGH to MEDIUM/LOW versus previous months,
   look into why before pasting.

**Nothing in step 5 or 6 happens automatically.** The automation computes and
publishes correct numbers; you still paste them into the actual sheet
yourself, every month.

---

## 4. How the AOP Forecast tool decides "real" vs. "forecast"

Every cell in `Cash Flow!row17` is a plain hardcoded number now — none of
them are formulas any more, so the real/forecast boundary can't be read from
the cell itself (an earlier version of this tool tried to; that broke once
the sheet's cells stopped being formulas, and got fixed).

Instead, `export_aop_data.py` computes the **most recently completed calendar
month** (relative to whenever the automation actually runs) and treats
everything up to and including it as real, everything after as forecast.
Concretely: if the pipeline runs on any day in September, the last real month
is August.

**This means the trigger for "this month becomes real" is running the
automation after you've typed in that month's actual number — not the
calendar date passing on its own.** Run it before updating the sheet for last
month, and the tool has no way to know you haven't gotten to it yet.

### Year 1 / 2 / 3 / 4 AOP summary cells

The sheet also has "Year N AOP" summary cells sitting *between* the monthly
columns (not just at the end), which used to break a straight copy-paste by
shifting every later column out of alignment. These are resolved by
**position**, not formula: whatever consecutive run of month-columns comes
right before a summary cell is what it covers. This works whether that cell
is a formula or a hardcoded number, and means a year straddling the
real/forecast boundary (e.g. 6 real + 6 forecast months) correctly produces
one blended average.

### The interactive tool's math (for a forecast month)

```
new_signup_orders  = total_new_signups (fixed, from the sheet's own
                      acquisition forecast) × your Monthly/3-Month/OTP mix %
new_signup_revenue = new_signup_orders × your price, with your discount %
                      applied ONLY to the first order (never a renewal)

renewal_orders / renewal_revenue = REAL, from actual past cohorts renewing
                      via the fitted sBG retention curve at THEIR OWN real
                      locked-in price — never touched by any input

+ compounding: a HYPOTHETICAL new signup created in an earlier forecast
  month also renews forward in later forecast months, at ITS OWN
  hypothetical price (never re-discounted) — so a price change ripples
  through every later month, not just the month it's made in

AOP = (renewal_revenue + new_signup_revenue) / (renewal_orders + new_signup_orders)
```

This mirrors the sheet's own real definition, confirmed by directly
inspecting the sheet's formulas: `Total Revenue ÷ Total Orders`, not revenue
÷ new acquisitions only.

---

## 5. Retention model (sBG) — key decisions and results

- **Data source**: only the APPENDIX cohort matrices (count tables +
  RETENTION % sub-table), never the per-subscriber ID/date export sitting
  next to them (unreliable).
- **A maturity filter is essential** — without it, fast-renewing customers
  get confirmed "not churned" before slow-to-resolve churners reveal
  themselves, silently flipping the apparent cohort trend direction.
- **Immediate (cycle-1) churners must stay in the panel** — an earlier
  version used second-order price as a feature, which silently dropped
  anyone who churned before a second order.
- **sBG only** for both plans — the beta-discrete-Weibull alternative was
  tested and explicitly dropped.
- **Validated results (last run)**: Monthly — new flat-tier numbers MAE
  0.0236 vs. old sheet numbers MAE 0.0358 (~34% better), 5-fold time-series
  CV, 125 held-out points. 1st-year LTV moves from £135.07 to £129.46
  (worse — the sheet had been too optimistic about months 7–12). 3-Month —
  directionally supportive but thinner data (4 folds, 42 held-out points,
  ~38% better on aggregate, individual folds disagree more). The month-9 fix
  alone improves 1st-year LTV from £126.83 to £129.93.
- **Not yet built**: a "Retention Tracker" sheet showing ML prediction vs.
  current sheet prediction vs. actual, frozen at generation date.

---

## 6. AOP forecast — key decisions and results

Three real bugs were found and fixed by validating against actual real
months, in order:

1. **Wrong denominator** — initially assumed "orders" meant new signups
   only; it's actually total orders (new + renewals).
2. **List price vs. actual amount paid** — discounts are large and common
   (confirmed: one real month's AOP was £41.87 using actual amounts paid,
   vs. £56.81 if list price were wrongly used).
3. **First-order discount doesn't carry to renewals** — subscribers renew at
   the recurring price locked in at signup, not their discounted first-order
   price, and not the current list price either. Fixed by matching each
   subscriber's actual renewal orders to their own real recurring price.

**Why current mix isn't just "last month's acquisition mix":** new-signup
mix has swung hard (from ~4% 3-Month at launch to ~78%+ later), but the
active base includes everyone who ever signed up, most of whom joined when
Monthly dominated. `estimate_current_mix.py` projects every historical
cohort forward through the live retention curve to estimate who's actually
still active today, rather than assuming the whole base looks like this
month's newest signups.

**Validation (typically ~4-5% average error, confidence HIGH)** — re-checked
every run against every known real historical month via time-series backtest
(the model never sees the future) plus rolling-origin cross-validation.
Numbers move slightly run to run as more real months accumulate; check
`outputs/aop_report.md` for the current figures.

**Known limitation**: the pipeline's own single recommendation
(`run_aop_pipeline.py`) holds plan mix FIXED going forward, matching the
sheet's own flat B8/B9 assumption. A mix-shift trend model (log-ratio
regression) was built and deliberately rejected — validated at only ~14%
average error / LOW confidence, too uncertain given the trend was still
accelerating with limited history at the time.

**The 3-month oscillation in the forecast is real, not a bug** — 3-Month
subscribers renew quarterly, so months where more of them land show a higher
blended AOP. The same pattern shows up in the real historical data.

---

## 7. If something breaks

- **A workflow step fails**: click into the failing step in the Actions run
  for the actual Python traceback — usually a missing/misnamed GitHub secret,
  a Google Drive permission issue, or a Shopify API auth problem.
- **A run gets stuck in "Queued" and won't cancel**: check
  githubstatus.com — this has happened before during a genuine GitHub Actions
  platform incident, not a repo problem. GitHub's own fix is to wait; stuck
  runs auto-resolve within ~24 hours.
- **Vercel deploy fails with "Deployment Blocked — commit author email not
  verified"**: your local git email doesn't match a verified email on your
  GitHub account. Fix just the affected commit with
  `git commit --amend --author="Name <verified@email.com>" --no-edit` — no
  need to change your global git config.
- **Numbers on the live page look wrong after a fix should have landed**:
  before assuming the fix is broken, confirm it actually made it into the
  repo — a rejected `git push` followed by a careless merge can silently drop
  local changes. Check the actual file on GitHub (or `grep` for a distinctive
  string from the fix) before re-debugging the logic itself.
- **Google Drive auth fails with `iam.serviceAccounts.getAccessToken` denied**:
  check the Workload Identity Federation binding in Google Cloud Console
  (IAM & Admin → Service Accounts → the pipeline service account →
  Principals with access) — the `principalSet://` string must exactly match
  `github-actions-pool/attribute.repository/<org>/<repo>`, with no
  duplication or typos.

---

## 8. Shopify data — scope and history

The `read_orders` API scope this pipeline uses only covers the **last 60
days** of order history. Getting full history back to launch would require
the `read_all_orders` scope, which needs Shopify's manual "protected customer
data" review/approval.

Since `data/customer_cohorts.csv` already contains the complete historical
dataset (built once from a manual CSV export), the ongoing automation only
needs to *append* new orders each run — 60 days comfortably covers that as
long as this workflow runs at least every ~2 months. If you ever need to
rebuild full history from scratch (e.g. a fresh Shopify store), you'd need to
either request `read_all_orders` or fall back to a manual CSV export for that
one-time rebuild (`extract_shopify_orders.py` supports both paths).

---

## 9. Required GitHub secrets

Settings → Secrets and variables → Actions:

| Secret | Purpose |
|---|---|
| `GDRIVE_PROJECT_NUMBER` | Google Cloud project number |
| `GDRIVE_WORKLOAD_POOL` | Workload Identity Pool ID (`github-actions-pool`) |
| `GDRIVE_SERVICE_ACCOUNT_EMAIL` | The service account being impersonated |
| `GDRIVE_FOLDER_ID` | Drive folder ID containing `model.xlsx` |
| `SHOPIFY_ACCESS_TOKEN` | Shopify Admin API token, `read_orders` scope |
| `SHOPIFY_STORE_DOMAIN` | Shopify store domain |

No long-lived Google service account key is ever stored — auth happens via
GitHub's own OIDC token exchanged at run time (Workload Identity Federation).
