"""
AI summarization using OpenAI API.
Produces neutral, factual summaries (3–5 bullet points or short paragraph).
"""
import logging
from typing import Optional

from openai import OpenAI

from src.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# Truncate very long content to stay within token limits and reduce cost
MAX_CONTENT_CHARS = 12000

SYSTEM_PROMPT = """You are a factual summarization assistant. Given a news article, produce a concise, neutral summary.
Output format: 3 to 5 bullet points, or one short paragraph. Be factual only; do not add opinion or speculation."""

USER_PROMPT_TEMPLATE = """Summarize this news article in a neutral, factual way (3–5 bullet points or one short paragraph):

Title: {title}

Content:
{content}"""


def _truncate(text: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars].rsplit(maxsplit=1)[0] + "…"


def summarize_with_openai(
    title: str,
    full_content: Optional[str],
    model: str = "gpt-4o-mini",
) -> Optional[str]:
    """
    Generate a concise factual summary using OpenAI.
    Returns None on failure or if content is empty (fail gracefully).
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; skipping summarization")
        return None

    content = (full_content or "").strip()
    if len(content) < 100:
        logger.debug("Content too short to summarize")
        return None

    content = _truncate(content)
    prompt = USER_PROMPT_TEMPLATE.format(title=title or "Untitled", content=content)

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        summary = (response.choices[0].message.content or "").strip()
        return summary if summary else None
    except Exception as e:
        logger.exception("OpenAI summarization failed: %s", e)
        return None
