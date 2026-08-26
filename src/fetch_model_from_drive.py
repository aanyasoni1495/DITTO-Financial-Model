"""
Downloads the latest model.xlsx from the shared Google Drive folder, using
Workload Identity Federation -- no service account KEY FILE involved (your
org's policy blocks creating those). Instead, this relies on the OIDC
token GitHub Actions automatically provides during a workflow run, which
Google exchanges for short-lived credentials scoped to impersonate the
ditto-pipeline-bot service account.

This script expects google-github-actions/auth to have already run as a
prior step in the workflow (see .github/workflows/monthly-refresh.yml) --
that action handles the actual token exchange and sets up Application
Default Credentials, so this script just uses the standard Google client
libraries as if a normal credential were already configured.

Usage:
    python3 src/fetch_model_from_drive.py
"""
import io
import os
import sys

from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def find_latest_xlsx(drive_service, folder_id):
    """Finds the most recently modified .xlsx file in the given folder --
    so whichever file was uploaded most recently is the one used, without
    needing an exact filename match."""
    query = (
        f"'{folder_id}' in parents and "
        f"mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and "
        f"trashed=false"
    )
    results = drive_service.files().list(
        q=query, orderBy="modifiedTime desc", pageSize=1,
        fields="files(id, name, modifiedTime)",
    ).execute()
    files = results.get("files", [])
    if not files:
        return None
    return files[0]


def download_file(drive_service, file_id, out_path):
    request = drive_service.files().get_media(fileId=file_id)
    with io.FileIO(out_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"  Download progress: {int(status.progress() * 100)}%")


if __name__ == "__main__":
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("ERROR: GDRIVE_FOLDER_ID environment variable not set.")
        sys.exit(1)

    credentials, project = default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    drive_service = build("drive", "v3", credentials=credentials)

    print(f"Looking for the latest .xlsx in Drive folder {folder_id}...")
    latest = find_latest_xlsx(drive_service, folder_id)
    if latest is None:
        print("ERROR: No .xlsx file found in the specified Drive folder. "
              "Make sure model.xlsx has been uploaded there.")
        sys.exit(1)

    print(f"Found: {latest['name']} (last modified {latest['modifiedTime']})")
    download_file(drive_service, latest["id"], "model.xlsx")
    print("Downloaded to model.xlsx")
