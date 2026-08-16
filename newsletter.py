"""Shared Gmail fetch/parse helpers used by both the standalone digest script
and the daily topic-fetch job."""

import base64
import os
import re

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
DEFAULT_SENDER = "dan@tldrnewsletter.com"


def get_gmail_service():
    if not os.path.exists(TOKEN_FILE) and os.environ.get("GMAIL_TOKEN_JSON"):
        with open(TOKEN_FILE, "w") as f:
            f.write(os.environ["GMAIL_TOKEN_JSON"])

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)

    if not creds or not creds.valid or not set(SCOPES).issubset(set(creds.scopes or [])):
        if creds and creds.expired and creds.refresh_token and set(SCOPES).issubset(set(creds.scopes or [])):
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_latest_email(service, sender: str, days: int):
    query = f"from:{sender} newer_than:{days}d"
    resp = service.users().messages().list(userId="me", q=query, maxResults=1).execute()
    messages = resp.get("messages", [])
    if not messages:
        return None
    return service.users().messages().get(userId="me", id=messages[0]["id"], format="full").execute()


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")


def extract_body(message: dict) -> str:
    payload = message["payload"]
    parts = payload.get("parts") or [payload]

    html_body, text_body = None, None
    stack = list(parts)
    while stack:
        part = stack.pop()
        if part.get("parts"):
            stack.extend(part["parts"])
            continue
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if not data:
            continue
        if mime == "text/html":
            html_body = _decode_part(data)
        elif mime == "text/plain":
            text_body = _decode_part(data)

    if html_body:
        soup = BeautifulSoup(html_body, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n")
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    return (text_body or "").strip()
