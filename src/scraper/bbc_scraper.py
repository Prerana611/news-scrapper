"""
BBC News web scraper: scrape articles directly from BBC section pages.
Extracts article URLs, titles, images, dates from https://www.bbc.com/news/* pages.
"""
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.config import SCRAPER_DELAY_SECONDS, DEFAULT_HEADERS

logger = logging.getLogger(__name__)


def _parse_bbc_date(date_str: Optional[str]) -> Optional[str]:
    """Parse BBC date string to ISO format."""
    if not date_str:
        return None
    try:
        # BBC uses formats like "2026-02-10T12:00:00.000Z" or "2 hours ago"
        if "T" in date_str and "Z" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat()
    except Exception:
        pass
    return None


def _extract_image_url(soup: BeautifulSoup, article_url: str) -> Optional[str]:
    """Extract article image from BBC page (og:image, or BBC's image tags)."""
    # Try og:image first (most reliable)
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        img_url = og_image["content"]
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            parsed = urlparse(article_url)
            img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
        return img_url

    # Try BBC's image components
    img_tag = soup.find("img", {"data-src": re.compile(r"ichef|ichef\.bbci")})
    if img_tag:
        src = img_tag.get("data-src") or img_tag.get("src")
        if src:
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                parsed = urlparse(article_url)
                return f"{parsed.scheme}://{parsed.netloc}{src}"
            return src

    # Try any image in article header/main
    main = soup.find("main") or soup.find("article")
    if main:
        img = main.find("img", src=re.compile(r"ichef|\.jpg|\.png"))
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                if src.startswith("//"):
                    return "https:" + src
                if src.startswith("/"):
                    parsed = urlparse(article_url)
                    return f"{parsed.scheme}://{parsed.netloc}{src}"
                return src
    return None


def _is_bbc_article_url(url: str) -> bool:
    """Check if URL is a BBC article (not section/navigation page)."""
    path = urlparse(url).path.lower()
    # Must contain /news/ or /sport/
    if "/news/" not in path and "/sport/" not in path:
        return False
    # Skip live pages, video pages, audio pages
    if any(skip in path for skip in ["/live/", "/av/", "/weather/", "/travel/", "/help/"]):
        return False
    
    # BBC articles have patterns like:
    # /news/articles/c5e74z5j8e1o (new format)
    # /news/world-us-canada-12345678 (old format with numeric ID at end)
    # /sport/football/12345678 (sport articles)
    
    # Check if it's an article by looking for:
    # 1. /articles/ path (new format)
    if "/articles/" in path:
        return True
    
    # 2. Numeric ID at end of path (old format: .../world-us-canada-12345678)
    # Extract last path segment
    path_parts = path.rstrip("/").split("/")
    if path_parts:
        last_segment = path_parts[-1]
        # If last segment has 5+ digits, it's likely an article
        if re.search(r'\d{5,}$', last_segment):
            return True
    
    # 3. Skip known section/category pages
    section_keywords = [
        r'world$', r'business$', r'technology$', r'science$', r'health$',
        r'entertainment$', r'arts$', r'video$', r'audio$', r'correspondents$',
        r'editors$', r'have_your_say$', r'england$', r'scotland$', r'wales$',
        r'northern_ireland$', r'politics$', r'education$', r'magazine$',
        r'uk$', r'us_canada$', r'africa$', r'asia$', r'australia$', r'europe$',
        r'latin_america$', r'middle_east$', r'pictures$', r'indepth$',
        r'verify$', r'ouch$', r'worklife$', r'culture$', r'future$', r'reel$',
        r'for_you$', r'more$', r'updated$', r'uk-politics$', r'world-politics$'
    ]
    for keyword in section_keywords:
        if re.search(keyword, path):
            return False
    
    # 4. Skip sport section pages (but allow sport articles)
    # Sport articles have numeric IDs: /sport/football/12345678
    if "/sport/" in path:
        # Check if it has numeric ID
        if re.search(r'\d{5,}', path):
            return True
        # Otherwise it's a section page like /sport/football
        return False
    
    # If none of the above, likely not an article
    return False


def scrape_bbc_section(section_url: str, category: str) -> list[dict[str, Any]]:
    """
    Scrape BBC section page (e.g., /news/business, /news/technology) for article links.
    Returns list of article entries: title, article_url, image_url, published_at, source.
    """
    entries: list[dict[str, Any]] = []
    try:
        resp = requests.get(section_url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)

        soup = BeautifulSoup(resp.text, "html.parser")

        # BBC uses various selectors for article links
        article_links = []
        # Main story cards - look for article links with numeric IDs or article patterns
        for link in soup.select('a[href*="/news/"], a[href*="/sport/"]'):
            href = link.get("href", "")
            if not href or href.startswith("#"):
                continue
            if href.startswith("/"):
                href = urljoin("https://www.bbc.com", href)
            # Skip non-article pages
            if not _is_bbc_article_url(href):
                continue
            if href not in article_links:
                article_links.append(href)

        # Extract article metadata from the listing page
        # Try more URLs but cap entries to ~100 to keep runtime reasonable
        for url in article_links[:150]:
            if len(entries) >= 100:
                break
            try:
                # Try to find title and image from the listing card
                link_elem = soup.find("a", href=url.replace("https://www.bbc.com", ""))
                if not link_elem:
                    link_elem = soup.find("a", href=url)

                title = None
                if link_elem:
                    # Title might be in the link text or a child element
                    title_elem = link_elem.find(["h2", "h3", "span"], class_=re.compile("title|headline"))
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    elif link_elem.get_text(strip=True):
                        title = link_elem.get_text(strip=True)[:200]

                if not title or len(title) < 10:
                    continue

                # Extract image from listing card
                image_url = None
                if link_elem:
                    img = link_elem.find("img")
                    if img:
                        src = img.get("src") or img.get("data-src")
                        if src:
                            if src.startswith("//"):
                                image_url = "https:" + src
                            elif src.startswith("/"):
                                image_url = urljoin("https://www.bbc.com", src)
                            else:
                                image_url = src

                entries.append({
                    "title": title,
                    "article_url": url,
                    "image_url": image_url,
                    "source": f"BBC {category}",
                    "published_at": None,  # Will be fetched from article page
                })
            except Exception as e:
                logger.debug("Failed to extract metadata for %s: %s", url, e)
                continue

        logger.info("Scraped %d articles from BBC %s (%s)", len(entries), category, section_url)
    except requests.RequestException as e:
        logger.exception("Request failed for BBC section %s: %s", section_url, e)
    except Exception as e:
        logger.exception("Unexpected error scraping BBC section %s: %s", section_url, e)
    return entries


def scrape_bbc_article_page(article_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Scrape full article page to get content, image, and published date.
    Returns (full_content, image_url, published_at_iso).
    """
    try:
        resp = requests.get(article_url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        time.sleep(SCRAPER_DELAY_SECONDS)

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract full content
        content_parts = []
        # BBC uses <article> or <main> with <div data-component="text-block">
        article = soup.find("article") or soup.find("main")
        if article:
            # Remove unwanted elements that might pollute text
            for unwanted in article.select("script, style, noscript, time, .visually-hidden, figcaption, [data-component='image-block'], [data-component='video-block']"):
                unwanted.decompose()
                
            for block in article.find_all("div", {"data-component": "text-block"}):
                text = block.get_text(separator=" ", strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
            # Fallback: get all paragraphs
            if not content_parts:
                for p in article.find_all("p"):
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)

        full_content = " ".join(content_parts).strip() if content_parts else None

        # Extract image
        image_url = _extract_image_url(soup, article_url)

        # Extract published date
        published_at = None
        time_elem = soup.find("time", {"data-testid": "timestamp"}) or soup.find("time")
        if time_elem:
            datetime_attr = time_elem.get("datetime") or time_elem.get("data-datetime")
            if datetime_attr:
                published_at = _parse_bbc_date(datetime_attr)
        if not published_at:
            # Try meta tag
            meta_time = soup.find("meta", property="article:published_time")
            if meta_time:
                published_at = _parse_bbc_date(meta_time.get("content"))

        return full_content, image_url, published_at
    except Exception as e:
        logger.exception("Failed to scrape BBC article page %s: %s", article_url, e)
        return None, None, None
