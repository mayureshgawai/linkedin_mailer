import json
import os
import re

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")


def _client():
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def _strip_code_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def extract_topics(newsletter_text: str) -> list[dict]:
    """Splits the TLDR newsletter into distinct topic options for LinkedIn posts."""
    prompt = (
        "Here is today's TLDR AI newsletter content. Extract 5-10 distinct news "
        "items suitable as LinkedIn post topics. Drop sponsor/ad content. "
        "Respond with ONLY a JSON array, no other text, where each item is:\n"
        '{"headline": "short headline", "summary": "1-2 sentence takeaway", '
        '"source_link": "url or null"}\n\n'
        f"{newsletter_text}"
    )
    response = _client().chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=1536,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _strip_code_fence(response.choices[0].message.content)
    return json.loads(raw)


def generate_linkedin_post(
    headline: str, summary: str, feedback: str | None = None, previous_draft: str | None = None
) -> str:
    instructions = (
        "Write a LinkedIn post (150-250 words) about the following AI news item. "
        "Write in a professional but conversational first-person voice, as if the "
        "poster is sharing their own take on the news. Include a hook opening line, "
        "2-3 short paragraphs, and end with a question or takeaway to invite "
        "engagement. No hashtag spam (max 3 relevant hashtags at the end). "
        "Do not use em dashes.\n\n"
        f"Headline: {headline}\nDetails: {summary}"
    )
    if feedback and previous_draft:
        instructions += (
            f"\n\nHere is the previous draft:\n{previous_draft}\n\n"
            f"Revise it based on this feedback: {feedback}"
        )

    response = _client().chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": instructions}],
    )
    return response.choices[0].message.content.strip()
