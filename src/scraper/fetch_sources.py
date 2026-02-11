"""
Fetch article entries from configured RSS/Atom feeds.
Uses feedparser; respects rate limiting via configurable delay.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import feedparser
import requests
from src.config import SCRAPER_DELAY_SECONDS, DEFAULT_HEADERS

logger = logging.getLogger(__name__)

# Default User-Agent; some feeds require it
# DEFAULT_HEADERS imported from config now


def _parse_date(entry: Any) -> datetime | None:
    """Parse published/updated date from feed entry into timezone-aware datetime."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, key, None)
        if parsed and len(parsed) >= 6:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def _get_link(entry: Any) -> str:
    """Get canonical article URL from entry (link or first link)."""
    link = getattr(entry, "link", None)
    if link:
        return link
    links = getattr(entry, "links", [])
    if links:
        return links[0].get("href", "") or ""
    return ""


def fetch_feed(feed_url: str, source_name: str) -> list[dict[str, Any]]:
    """
    Fetch a single RSS/Atom feed and return list of article entries.
    Each entry: title, article_url, source, published_at (ISO string or None).
    Does not fetch full article content here (done in scrape_article).
    """
    entries: list[dict[str, Any]] = []
    try:
        # feedparser can use a URL; we pass request headers via request
        resp = requests.get(
            feed_url,
            headers=DEFAULT_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)

        parsed = feedparser.parse(resp.content, response_headers=dict(resp.headers))
        if parsed.bozo and not getattr(parsed, "entries", None):
            logger.warning("Feed parse warning for %s: %s", source_name, parsed.bozo_exception)

        for entry in getattr(parsed, "entries", []) or []:
            link = _get_link(entry)
            if not link:
                continue
            title = (entry.get("title") or "").strip() or "(No title)"
            pub_dt = _parse_date(entry)
            published_at = pub_dt.isoformat() if pub_dt else None
            entries.append({
                "title": title,
                "article_url": link,
                "source": source_name,
                "published_at": published_at,
            })
        logger.info("Fetched %d entries from %s", len(entries), source_name)
    except requests.RequestException as e:
        logger.exception("Request failed for feed %s (%s): %s", feed_url, source_name, e)
    except Exception as e:
        logger.exception("Unexpected error fetching feed %s: %s", source_name, e)
    return entries


def fetch_all_feeds(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Fetch all given sources (each with name, feed_url).
    Returns combined list of article entries; one bad feed does not crash the job.
    """
    all_entries: list[dict[str, Any]] = []
    for src in sources:
        name = src.get("name") or "Unknown"
        feed_url = src.get("feed_url")
        if not feed_url:
            logger.warning("Source %s has no feed_url, skipping", name)
            continue
        entries = fetch_feed(feed_url, name)
        all_entries.extend(entries)
        time.sleep(SCRAPER_DELAY_SECONDS)
    return all_entries
