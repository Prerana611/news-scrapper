"""
Fetch full article content from a URL using newspaper3k + BeautifulSoup fallback.
Handles failures gracefully; one bad article does not crash the job.
"""
import hashlib
import logging
import time
from typing import Optional

import requests
from newspaper import Article
from bs4 import BeautifulSoup

from src.config import SCRAPER_DELAY_SECONDS, DEFAULT_HEADERS

logger = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    """SHA-256 hash of normalized content for deduplication."""
    normalized = (text or "").strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _fetch_html(url: str) -> Optional[str]:
    """Fetch raw HTML with basic error handling and rate limiting."""
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)
        return resp.text
    except requests.RequestException as e:
        logger.warning("HTTP request failed for %s: %s", url, e)
        return None


def _extract_with_newspaper(url: str, html: Optional[str] = None) -> Optional[str]:
    """Extract main article text using newspaper3k."""
    try:
        article = Article(url)
        if html:
            article.download(input_html=html)
        else:
            article.download()
        article.parse()
        text = (article.text or "").strip()
        return text if text else None
    except Exception as e:
        logger.debug("Newspaper extraction failed for %s: %s", url, e)
        return None


def _extract_with_bs4(html: str) -> Optional[str]:
    """Fallback: extract text from likely article containers."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style"]):
            tag.decompose()
        # Prefer article or main
        for selector in ("article", "main", "[role='main']", ".post-content", ".article-body", ".content"):
            node = soup.select_one(selector)
            if node:
                text = node.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    return text
        # Fallback to body
        body = soup.find("body")
        if body:
            return body.get_text(separator=" ", strip=True)[:50000]
        return None
    except Exception as e:
        logger.debug("BS4 extraction failed: %s", e)
        return None


def scrape_article_content(article_url: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Fetch full article content and image from article_url.
    Returns (full_content or None, image_url or None, content_hash).
    Hash is computed from URL + title if content could not be fetched (for deduplication).
    """
    html = _fetch_html(article_url)
    if not html:
        return None, None, content_hash(article_url)

    text = _extract_with_newspaper(article_url, html)
    if not text:
        text = _extract_with_bs4(html)

    # Extract image URL
    image_url = None
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Try og:image first
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(article_url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
            image_url = img_url
        # Fallback: find first large image in article
        if not image_url:
            article = soup.find("article") or soup.find("main")
            if article:
                img = article.find("img", src=True)
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        if src.startswith("//"):
                            image_url = "https:" + src
                        elif src.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(article_url)
                            image_url = f"{parsed.scheme}://{parsed.netloc}{src}"
                        else:
                            image_url = src
    except Exception as e:
        logger.debug("Image extraction failed: %s", e)

    if not text or len(text) < 50:
        return None, image_url, content_hash(article_url)

    return text, image_url, content_hash(text)
