"""
Fetches today's TLDR AI newsletter from Gmail and summarizes it with Claude.

One-time setup:
  1. pip install -r requirements.txt
  2. Google Cloud Console -> create/select a project -> enable "Gmail API"
  3. OAuth consent screen -> add yourself as a test user
  4. Credentials -> Create Credentials -> OAuth client ID -> "Desktop app"
     -> download the JSON, save it next to this script as credentials.json
  5. Put OPENROUTER_API_KEY and OPENROUTER_BASE_URL in a .env file next to
     this script (see .env.example)

Run:
  python tldr_digest.py
  python tldr_digest.py --sender dan@tldrnewsletter.com --days 1 --save
"""

import argparse
import base64
import os
import re
from datetime import date

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
DEFAULT_SENDER = "tldrnewsletter.com"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
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


def summarize_with_claude(newsletter_text: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    prompt = (
        "Here is today's TLDR AI newsletter content. Summarize it as a concise "
        "digest: 5-10 bullet points, each with the headline and a 1-sentence "
        "takeaway. Group related items. Drop sponsor/ad content.\n\n"
        f"{newsletter_text}"
    )
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Summarize today's TLDR newsletter with Claude.")
    parser.add_argument("--sender", default="dan@tldrnewsletter.com", help="Sender address/domain to filter on")
    parser.add_argument("--days", type=int, default=2, help="How many days back to search")
    parser.add_argument("--save", action="store_true", help="Save the summary to a dated .md file")
    args = parser.parse_args()

    service = get_gmail_service()
    message = fetch_latest_email(service, args.sender, args.days)
    if not message:
        print(f"No email from '{args.sender}' found in the last {args.days} day(s).")
        return

    body = extract_body(message)
    if not body:
        print("Found the email but couldn't extract any text from it.")
        return

    summary = summarize_with_claude(body)
    print(summary)

    if args.save:
        filename = f"tldr_digest_{date.today().isoformat()}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)
        print(f"\nSaved to {filename}")


if __name__ == "__main__":
    main()
