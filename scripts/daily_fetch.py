"""Daily job: fetch today's TLDR AI newsletter, split it into topic options,
store them, and email a topic-picker to the recipient. Run by Render Cron."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from app.db import Topic, get_session, init_db
from app.email_utils import build_topic_picker_email, notification_recipient, send_email
from app.llm_utils import extract_topics
from newsletter import DEFAULT_SENDER, extract_body, fetch_latest_email, get_gmail_service

load_dotenv()


def main():
    init_db()
    gmail = get_gmail_service()
    message = fetch_latest_email(gmail, DEFAULT_SENDER, days=2)
    if not message:
        print(f"No email from '{DEFAULT_SENDER}' found in the last 2 days.")
        return

    body = extract_body(message)
    if not body:
        print("Found the email but couldn't extract any text from it.")
        return

    topics_data = extract_topics(body)

    session = get_session()
    try:
        topics = [
            Topic(
                headline=t["headline"],
                summary=t["summary"],
                source_link=t.get("source_link"),
            )
            for t in topics_data
        ]
        session.add_all(topics)
        session.commit()

        base_url = os.environ["BASE_URL"].rstrip("/")
        send_email(
            gmail,
            notification_recipient(),
            "Today's TLDR AI topics",
            build_topic_picker_email(topics, base_url),
        )
        print(f"Inserted {len(topics)} topics and sent the picker email.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
