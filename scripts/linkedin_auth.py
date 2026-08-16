"""
One-time LinkedIn OAuth setup. Run this locally once to obtain an access
token and author URN, then paste both into your .env (local) and Render
environment variables as LINKEDIN_ACCESS_TOKEN / LINKEDIN_AUTHOR_URN.

Prerequisites:
  - A LinkedIn Developer app (developer.linkedin.com) with the "Sign In with
    LinkedIn using OpenID Connect" and "Share on LinkedIn" products added.
  - Under the app's Auth settings, add this exact redirect URL:
    http://localhost:8765/callback
  - LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET set in your local .env

Run:
  python scripts/linkedin_auth.py
"""

import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URI = "http://localhost:8765/callback"
SCOPES = "openid profile w_member_social"

_auth_code = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[{time.strftime('%H:%M:%S')}] Got request: {self.path}")
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _auth_code["code"] = params.get("code", [None])[0]
        _auth_code["state"] = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>Done, you can close this tab.</body></html>")

    def log_message(self, *args):
        pass


def main():
    client_id = os.environ["LINKEDIN_CLIENT_ID"]
    client_secret = os.environ["LINKEDIN_CLIENT_SECRET"]
    state = secrets.token_urlsafe(16)

    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )

    server = http.server.HTTPServer(("localhost", 8765), _CallbackHandler)

    def _run():
        try:
            server.handle_request()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Server thread crashed: {e!r}")

    thread = threading.Thread(target=_run)
    thread.start()

    print(f"[{time.strftime('%H:%M:%S')}] Open this URL in your browser to log in and approve:\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    thread.join(timeout=600)
    print(f"[{time.strftime('%H:%M:%S')}] Finished waiting (thread alive: {thread.is_alive()})")

    code = _auth_code.get("code")
    if not code or _auth_code.get("state") != state:
        raise SystemExit("Did not receive a valid authorization code. Aborting.")

    token_resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]
    expires_in = token_resp.json().get("expires_in")

    userinfo_resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    userinfo_resp.raise_for_status()
    member_id = userinfo_resp.json()["sub"]
    author_urn = f"urn:li:person:{member_id}"

    print("\nSuccess. Add these to your .env and Render environment variables:\n")
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    print(f"LINKEDIN_AUTHOR_URN={author_urn}")
    if expires_in:
        days = int(expires_in) // 86400
        print(f"\n(This token expires in ~{days} days; re-run this script to refresh it.)")


if __name__ == "__main__":
    main()
