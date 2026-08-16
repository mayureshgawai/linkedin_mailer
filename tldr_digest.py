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
import os
from datetime import date

from dotenv import load_dotenv

from newsletter import DEFAULT_SENDER, extract_body, fetch_latest_email, get_gmail_service

load_dotenv()

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")


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
    parser.add_argument("--sender", default=DEFAULT_SENDER, help="Sender address/domain to filter on")
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
