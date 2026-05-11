"""
Authentication for the FieldPro dashboard.

Works in two environments:
  1. Local: uses oauth-credentials.json + token.pickle (interactive browser auth)
  2. Streamlit Cloud: uses st.secrets["oauth_token"] (pre-generated token, no browser)
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import pickle
import json

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

CREDENTIALS_FILE = "oauth-credentials.json"
TOKEN_FILE = "token.pickle"


def _running_in_streamlit_cloud():
    """Detect if we're running on Streamlit Cloud (has st.secrets configured)."""
    try:
        import streamlit as st
        # On Streamlit Cloud, st.secrets exists and contains our token
        return "oauth_token" in st.secrets
    except Exception:
        return False


def _credentials_from_streamlit_secrets():
    """Build a Credentials object from values stored in Streamlit secrets."""
    import streamlit as st

    token_data = dict(st.secrets["oauth_token"])

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    # Always refresh on cloud — tokens may have expired since last refresh
    if creds.expired or not creds.valid:
        creds.refresh(Request())

    return creds


def _credentials_from_local_file():
    """Local development flow — interactive browser auth."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired — refreshing...")
            creds.refresh(Request())
        else:
            print("No valid token found — opening browser to log in...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
            print("Token saved.")

    return creds


def get_credentials():
    """Returns Google API credentials, using whichever path works in this environment."""
    if _running_in_streamlit_cloud():
        return _credentials_from_streamlit_secrets()
    return _credentials_from_local_file()


if __name__ == "__main__":
    print("Starting authentication...")
    creds = get_credentials()
    print()
    print("✓ Authentication successful!")
    if hasattr(creds, "client_id") and creds.client_id:
        print(f"  Client: {creds.client_id[:25]}...")