"""
First connection test for the FieldPro dashboard.
Opens a browser, asks you to log in with Google, and saves a token.
Run this once. After that, the saved token is reused automatically.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import pickle

# What we're asking permission to read.
# - analytics.readonly = read-only access to Google Analytics
# - webmasters.readonly = read-only access to Search Console
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

# Path to the credentials file you downloaded from Google Cloud
CREDENTIALS_FILE = "oauth-credentials.json"

# Where to save the access token after you log in (so you don't have to log in again next time)
TOKEN_FILE = "token.pickle"


def get_credentials():
    """Returns a credentials object that can be used to call Google APIs."""
    creds = None

    # If we already saved a token from a previous run, load it
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If the token is expired or doesn't exist, do the login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired — refreshing...")
            creds.refresh(Request())
        else:
            print("No valid token found — opening browser to log in...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the token for next time
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
            print("Token saved.")

    return creds


if __name__ == "__main__":
    print("Starting authentication...")
    creds = get_credentials()
    print()
    print("✓ Authentication successful!")
    print(f"  Logged in as: {creds.client_id[:20]}...")
    print(f"  Token saved to: {TOKEN_FILE}")