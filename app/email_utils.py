import base64
import os
from email.mime.text import MIMEText

BUTTON_STYLE = (
    "display:inline-block;padding:10px 20px;margin:6px 12px 6px 0;"
    "background:#0a66c2;color:#ffffff;text-decoration:none;border-radius:4px;"
    "font-family:sans-serif;font-weight:bold;"
)
SECONDARY_BUTTON_STYLE = BUTTON_STYLE.replace("#0a66c2", "#6c757d")


def _button(url: str, label: str, style: str = BUTTON_STYLE) -> str:
    return f'<a href="{url}" style="{style}">{label}</a>'


def send_email(service, to: str, subject: str, html_body: str):
    message = MIMEText(html_body, "html")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def build_topic_picker_email(topics, base_url: str) -> str:
    rows = []
    for t in topics:
        link = f"{base_url}/topics/{t.choose_token}/choose"
        rows.append(
            f'<div style="margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid #e0e0e0;">'
            f'<p style="font-family:sans-serif;font-weight:bold;margin:0 0 4px;">{t.headline}</p>'
            f'<p style="font-family:sans-serif;color:#444;margin:0 0 8px;">{t.summary}</p>'
            f"{_button(link, 'Write a post about this')}"
            f"</div>"
        )
    return (
        '<div style="max-width:600px;font-family:sans-serif;">'
        "<h2>Today's TLDR AI topics</h2>"
        "<p>Pick one to draft a LinkedIn post from:</p>"
        f"{''.join(rows)}"
        "</div>"
    )


def build_approval_email(post, base_url: str) -> str:
    approve_link = f"{base_url}/posts/{post.approve_token}/approve"
    regenerate_link = f"{base_url}/posts/{post.regenerate_token}/regenerate"
    feedback_note = ""
    if post.feedback:
        feedback_note = (
            f'<p style="font-family:sans-serif;color:#666;font-style:italic;">'
            f"Regenerated with your feedback: “{post.feedback}”</p>"
        )
    content_html = post.content.replace("\n", "<br>")
    return (
        '<div style="max-width:600px;font-family:sans-serif;">'
        f"<h2>Draft LinkedIn post (v{post.version})</h2>"
        f'<div style="background:#f5f5f5;padding:16px;border-radius:6px;white-space:pre-wrap;">{content_html}</div>'
        f"{feedback_note}"
        '<div style="margin-top:16px;">'
        f"{_button(approve_link, 'Approve & Post')}"
        f"{_button(regenerate_link, 'Regenerate', SECONDARY_BUTTON_STYLE)}"
        "</div>"
        "</div>"
    )


def notification_recipient() -> str:
    return os.environ["RECIPIENT_EMAIL"]
