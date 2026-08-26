# Monthly Refresh Automation

One button, on GitHub, that runs the entire pipeline end to end: pulls the
latest `model.xlsx` from Google Drive, pulls recent Shopify orders via the
API, refits the retention model, rebuilds cohort/pricing data, and
generates the AOP forecast -- then pushes everything back to the repo so
the Netlify AOV tool auto-updates.

## Running it

1. Upload the current `model.xlsx` to the shared Google Drive folder (the
   one shared with `ditto-pipeline-bot@ditto-financial-automation.iam.gserviceaccount.com`).
2. Go to this repo's **Actions** tab on GitHub.
3. Click **Monthly Refresh** in the left sidebar, then **Run workflow**.
4. Wait a few minutes. Check the run's log, or the **Summary** tab, for
   confirmation.
5. Once it finishes, `outputs/report.md` and `outputs/aop_report.md` have
   the updated findings, and the live Netlify AOV tool reflects the fresh
   data automatically.

No local setup, no credentials on anyone's machine -- anyone with repo
access can trigger this from the GitHub website.

## What it does, step by step

1. **Authenticates to Google Cloud** via Workload Identity Federation --
   no service account key file exists anywhere (blocked by org policy,
   and not needed: GitHub's own OIDC token is exchanged for short-lived
   Google credentials at run time).
2. **Downloads the latest `.xlsx`** from the shared Drive folder
   (`fetch_model_from_drive.py` -- picks the most recently modified file,
   so the filename doesn't need to match exactly).
3. **Refits the retention model** (`extract_data.py`, `run_pipeline.py`,
   `export_curves.py`) -- unchanged from the existing sBG pipeline.
4. **Pulls recent orders from Shopify's Admin API**
   (`fetch_shopify_orders_api.py`) -- last 60 days, per the `read_orders`
   scope (see "Why only 60 days" below). Merges into the existing
   `data/orders_clean.csv`, de-duplicated by order number, rather than
   replacing history.
5. **Rebuilds cohort/pricing data** (`build_customer_cohorts.py`,
   `detect_price_changes.py`) -- unchanged logic, just re-run on the
   refreshed order data.
6. **Runs the AOP forecast** (`run_aop_pipeline.py`) -- auto-detects the
   real/forecast boundary from `model.xlsx`'s own formulas, validates
   against every real historical month, forecasts forward.
7. **Commits and pushes** `data/`, `docs/`, `outputs/` -- never
   `model.xlsx` itself (deleted at the end of the run, and excluded from
   git via `.gitignore` regardless).

## Credential setup (already done -- reference only)

Six GitHub Secrets power this (Settings -> Secrets and variables ->
Actions):

| Secret | What it is |
|---|---|
| `GDRIVE_PROJECT_NUMBER` | Google Cloud project number (`566969837516`) |
| `GDRIVE_WORKLOAD_POOL` | Workload Identity Pool name (`github-actions-pool`) |
| `GDRIVE_SERVICE_ACCOUNT_EMAIL` | `ditto-pipeline-bot@ditto-financial-automation.iam.gserviceaccount.com` |
| `GDRIVE_FOLDER_ID` | The shared Drive folder's ID |
| `SHOPIFY_ACCESS_TOKEN` | Admin API token, `read_orders` scope only |
| `SHOPIFY_STORE_DOMAIN` | `ditto-daily.myshopify.com` |

**No service account key file exists anywhere** -- Google Cloud's
`iam.disableServiceAccountKeyCreation` org policy blocks creating one, and
Workload Identity Federation avoids needing one at all. GitHub Actions'
own OIDC token is exchanged for short-lived Google credentials at the
moment the workflow runs; nothing long-lived is stored.

The Shopify token was generated via the OAuth authorization code grant
(install flow), not the client-credentials grant -- confirmed this
produces a long-lived `shpat_...` token, not one that expires every 24
hours, so no token refresh step is needed in the workflow.

## Why only 60 days of Shopify order history

The `read_orders` scope Shopify grants by default only covers the last 60
days. Getting full history back to March 2025 would require the
`read_all_orders` scope, which needs Shopify's manual approval (a
"protected customer data" review). Since `data/customer_cohorts.csv`
already contains the complete historical dataset (built once from manual
CSV exports), the ongoing automation only needs to *append* new orders
each run, which 60 days comfortably covers as long as this workflow runs
at least every ~2 months. If you ever need to rebuild the full history
from scratch (e.g., a fresh Shopify store), you'd need to either request
`read_all_orders` or fall back to a manual CSV export for that one-time
rebuild.
