"""
AI summarization using OpenAI API.
Produces neutral, factual summaries (3–5 bullet points or short paragraph).
"""
import logging
from typing import Optional

from openai import OpenAI
from groq import Groq

from src.config import OPENAI_API_KEY, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

# Truncate very long content to stay within token limits and reduce cost
MAX_CONTENT_CHARS = 12000

SYSTEM_PROMPT = """You are a factual summarization assistant. Given a news article, produce a concise, neutral summary.
Write a single paragraph that is around 60 words (roughly 50–70 words). Be strictly factual; do not add opinion or speculation."""

USER_PROMPT_TEMPLATE = """Summarize this news article in a neutral, factual way as a single paragraph of about 60 words (roughly 50–70 words). Do not exceed 80 words:

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
    Generate a concise factual summary using Groq (preferred) or OpenAI.
    Returns None on failure or if content is empty (fail gracefully).
    """
    content = (full_content or "").strip()
    if len(content) < 100:
        logger.debug("Content too short to summarize")
        return None

    content = _truncate(content)
    prompt = USER_PROMPT_TEMPLATE.format(title=title or "Untitled", content=content)

    # Prefer Groq if key is configured; otherwise fall back to OpenAI.
    # Groq
    if GROQ_API_KEY:
        try:
            # Simple retry loop for 429 errors
            max_retries = 3
            last_exception = None
            import time
            import random

            for i in range(max_retries + 1):
                try:
                    client = Groq(api_key=GROQ_API_KEY)
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=500,
                    )
                    summary = (response.choices[0].message.content or "").strip()
                    break
                except Exception as e:
                    # Check if error message contains 429 or "Too Many Requests"
                    error_msg = str(e)
                    if "429" in error_msg or "Too Many Requests" in error_msg:
                        if i < max_retries:
                            delay = (2 ** i) + random.uniform(0, 1)
                            logger.warning("Groq Rate Limit (429). Retrying in %.2fs...", delay)
                            time.sleep(delay)
                            continue
                    last_exception = e
                    raise e
            if not summary and last_exception:
               raise last_exception

        except Exception as e:
            logger.exception("Groq summarization failed: %s", e)
            summary = ""
    else:
        if not OPENAI_API_KEY:
            logger.warning("No GROQ_API_KEY or OPENAI_API_KEY set; skipping summarization")
            return None
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
        except Exception as e:
            logger.exception("OpenAI summarization failed: %s", e)
            summary = ""

    if not summary:
        return None

    # Hard-limit to ~60 words in case the model goes over.
    words = summary.split()
    if len(words) > 60:
        summary = " ".join(words[:60]).rstrip(" .,!?:;") + "..."
    return summary
