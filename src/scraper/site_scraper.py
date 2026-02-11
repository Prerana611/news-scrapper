"""
Unified entry discovery for all sources.

Given a list of `sources` rows from Supabase, this module decides how to
discover article URLs for each source (BBC sections, Google News, generic RSS).

This keeps all scraping / feed-discovery logic in a single place so that the
daily job can just call `collect_entries_for_sources`.
"""
from __future__ import annotations

import logging
from typing import Any, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.config import SCRAPER_DELAY_SECONDS, DEFAULT_HEADERS
from src.scraper.bbc_scraper import scrape_bbc_section
from src.scraper.google_news_scraper import scrape_google_news_topic
from src.scraper.fetch_sources import fetch_feed

logger = logging.getLogger(__name__)


BBC_SECTION_URLS = {
    "Business": "https://www.bbc.com/news/business",
    "Technology": "https://www.bbc.com/news/technology",
    "Health": "https://www.bbc.com/news/health",
    "Sport": "https://www.bbc.com/sport",
    "News": "https://www.bbc.com/news",
}


def _scrape_fiercepharma_home(section_url: str, source_name: str) -> list[dict[str, Any]]:
    """
    Scrape FiercePharma homepage/section for article links.
    Best-effort: looks for article cards with links and optional images.
    """
    entries: list[dict[str, Any]] = []
    try:
        resp = requests.get(section_url, headers=DEFAULT_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        seen_urls: set[str] = set()
        # Look for anchor tags that point to fiercepharma articles
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not href or href.startswith("#"):
                continue
            if href.startswith("/"):
                href = f"https://www.fiercepharma.com{href}"
            if "fiercepharma.com" not in href:
                continue

            # Skip obvious non-article links (nav, login, etc.)
            if any(x in href for x in ["/search", "/login", "/about", "/privacy"]):
                continue

            # Title: prefer inner heading, otherwise link text
            title = None
            heading = link.find(["h1", "h2", "h3"])
            if heading:
                title = heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Optional image
            image_url = None
            img = link.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("//"):
                        image_url = "https:" + src
                    elif src.startswith("/"):
                        image_url = "https://www.fiercepharma.com" + src
                    else:
                        image_url = src

            entries.append(
                {
                    "title": title,
                    "article_url": href,
                    "image_url": image_url,
                    "source": source_name,
                    "published_at": None,
                }
            )

        logger.info("Scraped %d FiercePharma articles from %s", len(entries), section_url)
    except Exception as e:
        logger.exception("Failed to scrape FiercePharma section %s: %s", section_url, e)
    return entries


def _scrape_etpharma_home(section_url: str, source_name: str) -> list[dict[str, Any]]:
    """
    Scrape ET Pharma homepage/section for article links.
    Best-effort: looks for links under /news/ with titles and optional images.
    """
    entries: list[dict[str, Any]] = []
    try:
        resp = requests.get(section_url, headers=DEFAULT_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        seen_urls: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not href or href.startswith("#"):
                continue
            # Only news article URLs
            if "/news/" not in href:
                continue
            if href.startswith("/"):
                href = f"https://pharma.economictimes.indiatimes.com{href}"
            if "pharma.economictimes.indiatimes.com" not in href:
                continue

            # Title from inner text / heading
            title = None
            heading = link.find(["h1", "h2", "h3"])
            if heading:
                title = heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            image_url = None
            img = link.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    if src.startswith("//"):
                        image_url = "https:" + src
                    elif src.startswith("/"):
                        image_url = "https://pharma.economictimes.indiatimes.com" + src
                    else:
                        image_url = src

            entries.append(
                {
                    "title": title,
                    "article_url": href,
                    "image_url": image_url,
                    "source": source_name,
                    "published_at": None,
                }
            )

        logger.info("Scraped %d ET Pharma articles from %s", len(entries), section_url)
    except Exception as e:
        logger.exception("Failed to scrape ET Pharma section %s: %s", section_url, e)
    return entries


def _collect_for_source(src: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return a list of article entries for a single source.

    Each entry: {title, article_url, source, published_at, optional flags}.
    """
    name = (src.get("name") or "").strip()
    category = (src.get("category") or "").strip()
    feed_url = (src.get("feed_url") or "").strip()
    base_url = (src.get("base_url") or "").strip()

    domain = ""
    try:
        parsed = urlparse(base_url or feed_url or "")
        domain = (parsed.netloc or "").lower()
    except Exception:
        pass

    # 1) BBC: use dedicated HTML section scraper
    if name.startswith("BBC") and category in BBC_SECTION_URLS:
        logger.info("Using BBC section scraper for %s (%s)", name, category)
        return scrape_bbc_section(BBC_SECTION_URLS[category], category)

    # 2) FiercePharma: HTML scraping of homepage/section (no RSS)
    if "fiercepharma.com" in domain or "fierce pharma" in name.lower():
        section = base_url or "https://www.fiercepharma.com/"
        logger.info("Using FiercePharma HTML scraper for %s", section)
        return _scrape_fiercepharma_home(section, name or "Fierce Pharma")

    # 3) ET Pharma: HTML scraping of homepage/section (no RSS)
    if "pharma.economictimes.indiatimes.com" in domain or "et pharma" in name.lower():
        section = base_url or "https://pharma.economictimes.indiatimes.com/"
        logger.info("Using ET Pharma HTML scraper for %s", section)
        return _scrape_etpharma_home(section, name or "ET Pharma")

    # 4) Google News sources: use Google News RSS → then resolve to publisher
    if "google" in name.lower() or "news.google.com" in feed_url.lower() or "news.google.com" in domain:
        logger.info("Using Google News scraper for %s", name or domain or feed_url)
        return scrape_google_news_topic(feed_url or "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")

    # 5) Fallback: RSS feed if present (generic sources like Reuters, others)
    if feed_url:
        logger.info("Using generic RSS feed for %s", name or feed_url)
        return fetch_feed(feed_url, name or (domain or "Unknown"))

    logger.warning("Source %s has no discovery strategy (no feed_url/base_url); skipping", name or domain or "Unknown")
    return []


def collect_entries_for_sources(sources: List[dict[str, Any]], limit_per_source: int = 25) -> list[dict[str, Any]]:
    """
    Discover article entries for all active sources.
    One bad source should not crash the whole job.
    """
    all_entries: list[dict[str, Any]] = []
    for src in sources:
        try:
            entries = _collect_for_source(src)
            # Limit entries per source as requested
            if entries:
                all_entries.extend(entries[:limit_per_source])
        except Exception as e:
            logger.exception("Failed to collect entries for source %s: %s", src.get("name") or src, e)
    logger.info("Total entries collected from all sources (after limits): %d", len(all_entries))
    return all_entries

