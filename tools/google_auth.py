"""
tools/google_auth.py — Unified Google OAuth 2.0 credential manager.

Provides a single cached credential set that covers:
  • Gmail (read & write)
  • Google Calendar (create & edit)
  • Google Docs (read & edit)
  • Google Drive (file discovery)

First run triggers an interactive browser consent flow.  Subsequent runs
reuse the cached token.json, refreshing automatically when expired.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

_CREDENTIALS_FILE = HERE / os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
_TOKEN_FILE = HERE / os.environ.get("GOOGLE_TOKEN_FILE", "token.json")

_cached_creds = None


def get_google_credentials():
    """Return valid Google OAuth2 credentials, prompting login if needed."""
    global _cached_creds

    if _cached_creds and _cached_creds.valid:
        return _cached_creds

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise RuntimeError(
            "Google auth libraries not installed.  Run:\n"
            "  pip install google-api-python-client google-auth-httplib2 "
            "google-auth-oauthlib"
        )

    creds = None

    # Try loading existing token
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)

    # Refresh or re-authenticate
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None  # force re-auth

    if not creds or not creds.valid:
        if not _CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                f"Google credentials file not found at {_CREDENTIALS_FILE}.\n"
                "Download it from Google Cloud Console → APIs & Services → "
                "Credentials → OAuth 2.0 Client IDs → Download JSON.\n"
                "Save it as 'credentials.json' in the Hope project root."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(_CREDENTIALS_FILE), SCOPES,
        )
        creds = flow.run_local_server(port=0)
        # Persist for next run
        _TOKEN_FILE.write_text(creds.to_json())

    _cached_creds = creds
    return creds


def build_service(service_name: str, version: str):
    """Build and return an authorised Google API Resource client.

    Examples
    --------
    >>> svc = build_service("gmail", "v1")
    >>> svc = build_service("calendar", "v3")
    >>> svc = build_service("docs", "v1")
    >>> svc = build_service("drive", "v3")
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "google-api-python-client not installed.  Run:\n"
            "  pip install google-api-python-client"
        )
    creds = get_google_credentials()
    return build(service_name, version, credentials=creds)


def is_google_oauth_configured() -> bool:
    """Return True if the credentials file exists (even if not yet authorised)."""
    return _CREDENTIALS_FILE.exists()

