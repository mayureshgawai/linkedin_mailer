import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from app.db import Post, Topic, get_session
from app.email_utils import build_approval_email, notification_recipient, send_email
from app.linkedin_utils import post_to_linkedin
from app.llm_utils import generate_linkedin_post
from newsletter import get_gmail_service

load_dotenv()

app = FastAPI()


def _base_url() -> str:
    return os.environ["BASE_URL"].rstrip("/")


def _page(title: str, body: str) -> HTMLResponse:
    html = (
        f'<html><head><title>{title}</title></head>'
        f'<body style="font-family:sans-serif;max-width:600px;margin:60px auto;">'
        f"<h2>{title}</h2>{body}</body></html>"
    )
    return HTMLResponse(html)


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/topics/{token}/choose")
def choose_topic(token: str):
    session = get_session()
    try:
        topic = session.query(Topic).filter_by(choose_token=token).first()
        if not topic or topic.status != "pending":
            return _page("Link no longer valid", "<p>This topic was already picked or has expired.</p>")

        topic.status = "selected"
        content = generate_linkedin_post(topic.headline, topic.summary)
        post = Post(topic_id=topic.id, version=1, content=content)
        session.add(post)
        session.commit()

        gmail = get_gmail_service()
        send_email(
            gmail,
            notification_recipient(),
            f"Draft LinkedIn post: {topic.headline}",
            build_approval_email(post, _base_url()),
        )
        return _page("Draft generated", "<p>Check your email to approve or regenerate it.</p>")
    finally:
        session.close()


@app.get("/posts/{token}/approve")
def approve_post(token: str):
    session = get_session()
    try:
        post = session.query(Post).filter_by(approve_token=token).first()
        if not post or post.status != "pending_approval":
            return _page("Link no longer valid", "<p>This draft was already handled or has expired.</p>")

        urn = post_to_linkedin(post.content)
        post.status = "posted"
        post.linkedin_urn = urn
        post.posted_at = datetime.utcnow()
        session.commit()
        return _page("Posted!", "<p>Your post is live on LinkedIn.</p>")
    finally:
        session.close()


@app.get("/posts/{token}/regenerate")
def regenerate_form(token: str):
    session = get_session()
    try:
        post = session.query(Post).filter_by(regenerate_token=token).first()
        if not post or post.status != "pending_approval":
            return _page("Link no longer valid", "<p>This draft was already handled or has expired.</p>")

        body = (
            f'<form method="post" action="/posts/{token}/regenerate">'
            '<textarea name="feedback" rows="4" style="width:100%;" '
            'placeholder="What should change? e.g. shorter, more casual tone, focus on X"></textarea><br><br>'
            '<button type="submit" style="padding:10px 20px;background:#0a66c2;color:#fff;'
            'border:none;border-radius:4px;">Regenerate</button>'
            "</form>"
        )
        return _page("Give feedback", body)
    finally:
        session.close()


@app.post("/posts/{token}/regenerate")
def regenerate_post(token: str, feedback: str = Form(default="")):
    session = get_session()
    try:
        old_post = session.query(Post).filter_by(regenerate_token=token).first()
        if not old_post or old_post.status != "pending_approval":
            return _page("Link no longer valid", "<p>This draft was already handled or has expired.</p>")

        old_post.status = "superseded"
        topic = old_post.topic
        content = generate_linkedin_post(
            topic.headline, topic.summary, feedback=feedback or None, previous_draft=old_post.content
        )
        new_post = Post(
            topic_id=topic.id,
            version=old_post.version + 1,
            content=content,
            feedback=feedback or None,
        )
        session.add(new_post)
        session.commit()

        gmail = get_gmail_service()
        send_email(
            gmail,
            notification_recipient(),
            f"Draft LinkedIn post (v{new_post.version}): {topic.headline}",
            build_approval_email(new_post, _base_url()),
        )
        return _page("New draft generated", "<p>Check your email to approve or regenerate it.</p>")
    finally:
        session.close()
