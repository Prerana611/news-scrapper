"""
Google News scraper: fetch articles from Google News RSS and resolve to full content.
Google News RSS gives encoded URLs that redirect to publisher sites.
"""
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

from src.config import SCRAPER_DELAY_SECONDS, DEFAULT_HEADERS
from src.scraper.scrape_article import scrape_article_content, content_hash

logger = logging.getLogger(__name__)


def resolve_google_news_url(google_url: str) -> Optional[str]:
    """
    Resolve a Google News URL to the actual publisher URL.
    Google News URLs are encoded and redirect through Google's servers.
    """
    try:
        # Google News RSS URLs are in format:
        # https://news.google.com/rss/articles/CBMi... (encoded)
        # These are base64-like encoded URLs that need to be decoded
        
        # Strategy 1: Try to follow redirects (sometimes works with proper headers)
        session = requests.Session()
        # Mimic a real browser more closely
        headers = {
            **DEFAULT_HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://news.google.com/",
        }
        
        resp = session.get(
            google_url,
            headers=headers,
            timeout=15,
            allow_redirects=True,
        )
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)
        
        final_url = resp.url
        # If we got redirected to a real publisher site, return it
        if not final_url.startswith("https://news.google.com"):
            return final_url
        
        # Strategy 2: Parse the Google News page to find the external link
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Look for the article title link (usually the main external link)
        # Google News uses various layouts, try multiple selectors
        selectors = [
            "a[target='_blank'][rel='noopener']",  # External links open in new tab
            "article a[href^='http']",  # Article links
            ".DY5T1d a[href^='http']",  # Headline links
            "a[href^='http']:not([href*='google.com'])",  # Any non-Google link
        ]
        
        for selector in selectors:
            link = soup.select_one(selector)
            if link:
                href = link.get("href", "")
                if href and href.startswith("http") and "google.com" not in urlparse(href).netloc:
                    return href
        
        # Strategy 3: Look for all links and filter
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Skip Google internal links
            if href.startswith("http") and "google.com" not in urlparse(href).netloc:
                return href
        
        # Strategy 4: Decode the article ID from URL (experimental)
        # Google News uses base64-like encoding that sometimes contains the URL
        # This is complex and may break, so use as last resort
        
        return final_url
    except requests.RequestException as e:
        logger.debug("Failed to resolve Google News URL %s: %s", google_url[:60], e)
        return None
    except Exception as e:
        logger.debug("Error resolving Google News URL: %s", e)
        return None


def scrape_google_news_topic(topic_url: str = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en") -> list[dict[str, Any]]:
    """
    Scrape Google News from RSS feed and resolve to full articles.
    Returns list of article entries with full_content and image_url.
    """
    import feedparser
    
    entries: list[dict[str, Any]] = []
    try:
        resp = requests.get(topic_url, headers=DEFAULT_HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)
        
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not getattr(parsed, "entries", None):
            logger.warning("Google News RSS parse warning: %s", parsed.bozo_exception)
        
        for entry in getattr(parsed, "entries", [])[:30]:  # Limit to top 30 articles
            title = (entry.get("title") or "").strip()
            google_url = entry.get("link", "")
            
            if not title or not google_url:
                continue
            
            # Parse published date
            published_at = None
            for key in ("published_parsed", "updated_parsed"):
                parsed_date = getattr(entry, key, None)
                if parsed_date and len(parsed_date) >= 6:
                    from datetime import datetime, timezone
                    try:
                        dt = datetime(*parsed_date[:6], tzinfo=timezone.utc)
                        published_at = dt.isoformat()
                    except (TypeError, ValueError):
                        pass
                    break
            
            # Try to get source name from the entry
            source_name = "Google News"
            if hasattr(entry, "source") and entry.source:
                source_name = entry.source.get("title", "Google News")
            
            # Extract source from title if format is "Title - Source"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    source_name = parts[1].strip()
            
            entries.append({
                "title": title,
                "article_url": google_url,  # This is the Google News URL, will resolve later
                "source": source_name,
                "published_at": published_at,
                "is_google_news_url": True,
            })
        
        logger.info("Fetched %d entries from Google News RSS", len(entries))
    except Exception as e:
        logger.exception("Failed to fetch Google News: %s", e)
    
    return entries


def fetch_google_news_full_content(google_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetch full content from a Google News URL by resolving to publisher site.
    Returns (full_content, image_url, resolved_url).
    """
    resolved_url = resolve_google_news_url(google_url)
    if not resolved_url:
        logger.debug("Could not resolve Google News URL: %s", google_url[:60])
        return None, None, None
    
    # Use the generic scraper to get content from the resolved URL
    full_content, image_url, _ = scrape_article_content(resolved_url)
    
    return full_content, image_url, resolved_url
